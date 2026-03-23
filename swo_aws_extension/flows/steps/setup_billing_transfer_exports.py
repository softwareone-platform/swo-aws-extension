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
from swo_aws_extension.flows.jobs.billing_journal.setup.cost_usage_reports import (
    CostUsageReportsSetupService,
)
from swo_aws_extension.flows.jobs.billing_journal.setup.cost_usage_reports import (
    extract_billing_view_id as _extract_billing_view_id,
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


def extract_billing_view_id(billing_view_arn: str) -> str:
    """Extract the billing view ID from a BILLING_TRANSFER ARN."""
    return _extract_billing_view_id(billing_view_arn)


class SetupBillingTransferExports(BasePhaseStep):
    """Create CUR2 exports for all active BILLING_TRANSFER views."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._setup_service = CostUsageReportsSetupService()

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
        logger.info(
            "%s - Action - Setting up billing transfer exports for account %s to s3://%s/%s",
            context.order_id,
            mpa_id,
            s3_bucket,
            s3_prefix,
        )
        if context.aws_client is None:
            raise UnexpectedStopError(
                title="Billing Transfer Exports Setup",
                message=f"{context.order_id} - AWS client is not initialized",
            )
        try:
            setup_result = self._setup_service.create_billing_exports(
                context.aws_client,
                context.pm_account_id,
                mpa_id,
            )
        except AWSError as error:
            raise UnexpectedStopError(
                title="Billing Transfer Exports Setup",
                message=(
                    f"{context.order_id} - Failed to setup billing exports for account"
                    f" {mpa_id}: {error!s}"
                ),
            ) from error
        logger.info(
            "%s - Next - Billing transfer exports: %d created, %d skipped, %d failed",
            context.order_id,
            setup_result.created_exports,
            setup_result.skipped_exports,
            setup_result.failed_exports,
        )

    @override
    def post_step(self, client: MPTClient, context: PurchaseContext) -> None:
        """Advance the phase to COMPLETED and persist the order."""
        context.order = set_phase(context.order, PhasesEnum.COMPLETED)
        context.order = update_order(
            client, context.order_id, parameters=context.order["parameters"]
        )
