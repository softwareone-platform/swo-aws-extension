import logging
from typing import override

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.aws.errors import AWSError, S3BucketAlreadyOwnedError
from swo_aws_extension.config import Config
from swo_aws_extension.constants import (
    S3_BILLING_EXPORT_BUCKET_TEMPLATE,
    S3_BILLING_EXPORT_PREFIX_TEMPLATE,
    PhasesEnum,
)
from swo_aws_extension.flows.jobs.billing_journal.setup.cost_usage_reports import (
    CostUsageReportsSetupService,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.errors import (
    SkipStepError,
    UnexpectedStopError,
)
from swo_aws_extension.parameters import (
    get_mpa_account_id,
    get_phase,
    set_phase,
)

logger = logging.getLogger(__name__)


class CreateBillingExportBucket(BasePhaseStep):
    """Create an S3 bucket for CUR2 billing transfer exports.

    Runs at the ``COMPLETED`` phase (alongside CRM ticket steps), then transitions
    the order to ``SETUP_BILLING_TRANSFER_EXPORTS`` so the next step can create the
    actual CUR2 exports.
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._setup_service = CostUsageReportsSetupService()

    @override
    def pre_step(self, context: PurchaseContext) -> None:
        """Skip if not in the COMPLETED phase."""
        phase = get_phase(context.order)
        if phase != PhasesEnum.COMPLETED:
            raise SkipStepError(
                f"{context.order_id} - Next - Current phase is '{phase}', skipping as it"
                f" is not '{PhasesEnum.COMPLETED}'"
            )

    @override
    def process(self, client: MPTClient, context: PurchaseContext) -> None:
        """Create the S3 bucket for CUR2 billing transfer exports."""
        pm_account_id = context.pm_account_id
        mpa_id = get_mpa_account_id(context.order)
        bucket_name = S3_BILLING_EXPORT_BUCKET_TEMPLATE.format(pm_account_id=pm_account_id)
        prefix = S3_BILLING_EXPORT_PREFIX_TEMPLATE.format(mpa_account_id=mpa_id)
        if context.aws_client is None:
            raise UnexpectedStopError(
                title="S3 Billing Export Bucket Creation",
                message=f"{context.order_id} - AWS client is not initialized",
            )
        logger.info(
            "%s - Action - Creating S3 billing export bucket: %s",
            context.order_id,
            bucket_name,
        )
        try:
            self._setup_service.setup_s3_bucket(context.aws_client, pm_account_id)
        except S3BucketAlreadyOwnedError:
            logger.info(
                "%s - S3 bucket: %s already exists and is owned by %s account",
                context.order_id,
                bucket_name,
                pm_account_id,
            )
        except AWSError as error:
            raise UnexpectedStopError(
                title="S3 Billing Export Bucket Creation",
                message=(
                    f"{context.order_id} - Failed to create S3 bucket {bucket_name}: {error!s}"
                ),
            ) from error

        logger.info(
            "%s - Next - S3 billing export bucket setup completed: %s with prefix: %s",
            context.order_id,
            bucket_name,
            prefix,
        )

    @override
    def post_step(self, client: MPTClient, context: PurchaseContext) -> None:
        """Advance the phase to SETUP_BILLING_TRANSFER_EXPORTS and persist the order."""
        context.order = set_phase(context.order, PhasesEnum.SETUP_BILLING_TRANSFER_EXPORTS)
        context.order = update_order(
            client, context.order_id, parameters=context.order["parameters"]
        )
