import logging
from typing import override

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.config import Config
from swo_aws_extension.constants import (
    S3_BILLING_EXPORT_BUCKET_TEMPLATE,
    S3_BILLING_EXPORT_PREFIX_TEMPLATE,
    PhasesEnum,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.errors import SkipStepError, UnexpectedStopError
from swo_aws_extension.parameters import (
    get_mpa_account_id,
    get_phase,
    set_phase,
)

logger = logging.getLogger(__name__)

_BILLING_TRANSFER_PREFIX = "billing-transfer-"
_VIEW_S3_PREFIX_TEMPLATE = "{s3_prefix}/{billing_view_tail}"


def extract_billing_view_id(billing_view_arn: str) -> str:
    """Extract the billing view ID from a BILLING_TRANSFER ARN.

    Args:
        billing_view_arn: Full ARN of the billing view.

    Returns:
        The unique ID portion after the ``billing-transfer-`` prefix, or the
        last path segment of the ARN if the prefix is absent.

    Example:
        ``arn:aws:billing::123456789012:billingview/billing-transfer-abc123``
        returns ``abc123``.
    """
    tail = billing_view_arn.rsplit("/", 1)[-1]
    if tail.startswith(_BILLING_TRANSFER_PREFIX):
        return tail[len(_BILLING_TRANSFER_PREFIX) :]
    return tail


class SetupBillingTransferExports(BasePhaseStep):
    """Create CUR2 exports for all active BILLING_TRANSFER views."""

    def __init__(self, config: Config) -> None:
        self._config = config

    @override
    def pre_step(self, context: PurchaseContext) -> None:
        """Skip if not in the correct phase."""
        phase = get_phase(context.order)
        if phase != PhasesEnum.SETUP_BILLING_TRANSFER_EXPORTS:
            raise SkipStepError(
                f"{context.order_id} - Next - Current phase is '{phase}', skipping as it"
                f" is not '{PhasesEnum.SETUP_BILLING_TRANSFER_EXPORTS}'"
            )

    @override
    def process(self, client: MPTClient, context: PurchaseContext) -> None:
        """List billing transfer views and create a CUR2 export for each new one."""
        mpa_id = get_mpa_account_id(context.order)
        s3_bucket = S3_BILLING_EXPORT_BUCKET_TEMPLATE.format(pm_account_id=context.pm_account_id)
        s3_prefix = S3_BILLING_EXPORT_PREFIX_TEMPLATE.format(mpa_account_id=mpa_id)
        billing_views, existing_arns = self._fetch_billing_data(
            context, mpa_id, s3_bucket, s3_prefix
        )
        logger.info(
            "%s - Action - Setting up billing transfer exports for account %s to s3://%s/%s",
            context.order_id,
            mpa_id,
            s3_bucket,
            s3_prefix,
        )
        self._process_billing_views(context, billing_views, existing_arns, s3_bucket, s3_prefix)

    @override
    def post_step(self, client: MPTClient, context: PurchaseContext) -> None:
        """Advance the phase to COMPLETED and persist the order."""
        context.order = set_phase(context.order, PhasesEnum.COMPLETED)
        context.order = update_order(
            client, context.order_id, parameters=context.order["parameters"]
        )

    def _fetch_billing_data(
        self,
        context: PurchaseContext,
        mpa_id: str,
        s3_bucket: str,
        s3_prefix: str,
    ) -> tuple[list, set]:
        """Fetch billing views and existing exports, raising on failure."""
        try:
            billing_views = context.aws_client.get_current_billing_view_by_account_id(mpa_id)
        except AWSError as error:
            raise UnexpectedStopError(
                title="Billing Transfer Exports Setup",
                message=(
                    f"{context.order_id} - Failed to retrieve billing views for account"
                    f" {mpa_id}: {error!s}"
                ),
            ) from error
        try:
            existing_arns = context.aws_client.list_existing_billing_exports(s3_bucket, s3_prefix)
        except AWSError as error:
            raise UnexpectedStopError(
                title="Billing Transfer Exports Setup",
                message=(
                    f"{context.order_id} - Failed to list existing exports for account"
                    f" {mpa_id}: {error!s}"
                ),
            ) from error
        return billing_views, existing_arns

    def _process_billing_views(
        self,
        context: PurchaseContext,
        billing_views: list,
        existing_arns: set,
        s3_bucket: str,
        s3_prefix: str,
    ) -> None:
        """Process each billing view, creating exports where missing."""
        counts: dict = {"created": 0, "skipped": 0, "failed": 0}
        for billing_view in billing_views:
            billing_view_arn = billing_view.get("billingViewArn", "")
            if not billing_view_arn:
                logger.warning(
                    "%s - Warning - Billing view has no ARN, skipping: %s",
                    context.order_id,
                    billing_view,
                )
                continue
            if billing_view_arn in existing_arns:
                logger.info(
                    "%s - Skip - Export already exists for billing view %s",
                    context.order_id,
                    billing_view_arn,
                )
                counts["skipped"] += 1
                continue
            if self._create_single_export(
                context, billing_view, billing_view_arn, s3_bucket, s3_prefix
            ):
                counts["created"] += 1
            else:
                counts["failed"] += 1
        logger.info(
            "%s - Next - Billing transfer exports: %d created, %d skipped, %d failed",
            context.order_id,
            counts["created"],
            counts["skipped"],
            counts["failed"],
        )

    def _create_single_export(
        self,
        context: PurchaseContext,
        billing_view: dict,
        billing_view_arn: str,
        s3_bucket: str,
        s3_prefix: str,
    ) -> bool:
        """Attempt to create a CUR2 export for one billing view.

        Returns:
            True if the export was created successfully, False otherwise.
        """
        source_account_id = billing_view.get("sourceAccountId", get_mpa_account_id(context.order))
        billing_view_tail = billing_view_arn.rsplit("/", 1)[-1]
        billing_view_id = extract_billing_view_id(billing_view_arn)
        view_s3_prefix = _VIEW_S3_PREFIX_TEMPLATE.format(
            s3_prefix=s3_prefix,
            billing_view_tail=billing_view_tail,
        )
        export_name = f"{source_account_id}-{billing_view_id}"
        try:
            export_arn = context.aws_client.create_billing_export(
                billing_view_arn=billing_view_arn,
                export_name=export_name,
                s3_bucket=s3_bucket,
                s3_prefix=view_s3_prefix,
            )
        except AWSError as error:
            logger.warning(
                "%s - Warning - Failed to create billing export for view %s: %s",
                context.order_id,
                billing_view_arn,
                error,
            )
            return False
        logger.info(
            "%s - Action - Created billing export %s for view %s",
            context.order_id,
            export_arn,
            billing_view_arn,
        )
        return True
