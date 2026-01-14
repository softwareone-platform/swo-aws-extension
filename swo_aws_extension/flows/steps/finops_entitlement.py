import datetime as dt
import logging
from typing import override

from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.airtable.finops_table import FinOpsEntitlementsTable
from swo_aws_extension.constants import FinOpsStatusEnum
from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.errors import SkipStepError, UnexpectedStopError
from swo_aws_extension.parameters import get_responsibility_transfer_id
from swo_aws_extension.swo.finops.client import get_ffc_client
from swo_aws_extension.swo.finops.errors import FinOpsHttpError

logger = logging.getLogger(__name__)


class TerminateFinOpsEntitlementStep(BasePhaseStep):
    """Step to terminate FinOps entitlement associated with the responsibility transfer."""

    def __init__(self, config) -> None:
        self._config = config

    @override
    def pre_step(self, context: InitialAWSContext) -> None:
        """Pre-step checks before terminating FinOps entitlement."""
        responsibility_transfer_id = get_responsibility_transfer_id(context.order)
        if not responsibility_transfer_id:
            raise SkipStepError(
                f"{context.order_id} - Responsibility transfer ID is missing in the order. "
                f"Skipping FinOps entitlement termination."
            )

    @override
    def process(self, client: MPTClient, context: InitialAWSContext) -> None:
        """Terminates the FinOps entitlement associated with the responsibility transfer."""
        logger.info("%s - Managing FinOps entitlement termination.", context.order_id)
        entitlements_table = FinOpsEntitlementsTable()
        finops_entitlements = entitlements_table.get_by_agreement_id(context.agreement["id"])
        for finops_entitlement in finops_entitlements:
            try:
                self._terminate_finops_entitlement(context, finops_entitlement)
            except FinOpsHttpError as exception:
                raise UnexpectedStopError(
                    title="FinOps Entitlement Termination",
                    message=(
                        f"{context.order_id} - unhandled exception while terminating"
                        f" FinOps entitlement for account {finops_entitlement.account_id}."
                    ),
                ) from exception

            entitlements_table.update_status_and_usage_date(
                finops_entitlement,
                FinOpsStatusEnum.TERMINATED,
                dt.datetime.now(dt.UTC).isoformat(),
            )

    @override
    def post_step(self, client: MPTClient, context: InitialAWSContext) -> None:
        """Post-step actions after terminating FinOps entitlement."""
        logger.info("%s - Completed FinOps entitlement termination step.", context.order_id)

    def _terminate_finops_entitlement(self, context, finops_entitlement):
        finops_client = get_ffc_client()
        entitlement = finops_client.get_entitlement_by_datasource(finops_entitlement.account_id)
        if not entitlement:
            logger.info(
                "%s - FinOps entitlement for account %s not found in FinOps. "
                "Removing from Airtable.",
                context.order_id,
                finops_entitlement.account_id,
            )
            return
        if entitlement["status"] == "new":
            finops_client.delete_entitlement(entitlement["id"])
            logger.info("%s - Deleted FinOps entitlement %s.", context.order_id, entitlement["id"])
        elif entitlement["status"] == "active":
            finops_client.terminate_entitlement(entitlement["id"])
            logger.info(
                "%s - Terminated FinOps entitlement %s.",
                context.order_id,
                entitlement["id"],
            )
