import logging
from typing import override

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.config import Config
from swo_aws_extension.constants import (
    BASIC_PRICING_PLAN_ARN,
    INVALID_RESPONSIBILITY_TRANSFER_STATUS,
    OrderQueryingTemplateEnum,
    PhasesEnum,
    ResponsibilityTransferStatus,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.errors import (
    ConfigurationStepError,
    FailStepError,
    QueryStepError,
    SkipStepError,
)
from swo_aws_extension.parameters import (
    get_mpa_account_id,
    get_phase,
    get_responsibility_transfer_id,
    set_billing_group_arn,
    set_phase,
)

logger = logging.getLogger(__name__)


class CheckBillingTransferInvitation(BasePhaseStep):
    """Check Billing Transfer Invitation step."""

    def __init__(self, config: Config):
        self._config = config

    @override
    def pre_step(self, context: PurchaseContext) -> None:
        """Hook to run before the step processing."""
        phase = get_phase(context.order)
        if phase != PhasesEnum.CHECK_BILLING_TRANSFER_INVITATION:
            raise SkipStepError(
                f"{context.order_id} - Next - Current phase is '{phase}', skipping as it"
                f" is not '{PhasesEnum.CHECK_BILLING_TRANSFER_INVITATION}'"
            )

        if not get_responsibility_transfer_id(context.order):
            raise ConfigurationStepError(
                "Error checking billing transfer status",
                "Billing transfer invitation ID is missing in the order.",
            )

    @override
    def process(self, client: MPTClient, context: PurchaseContext) -> None:
        """Check billing transfer invitation."""
        logger.info("%s - Action - Checking billing transfer invitation status", context.order_id)

        transfer_id = get_responsibility_transfer_id(context.order)
        transfer_details = context.aws_client.get_responsibility_transfer_details(
            transfer_id=transfer_id
        )

        status = transfer_details.get("ResponsibilityTransfer", {}).get("Status")
        logger.info(
            "%s - Info - Billing transfer invitation %s status: %s",
            context.order_id,
            transfer_id,
            status,
        )
        if status == ResponsibilityTransferStatus.ACCEPTED:
            logger.info(
                "%s - Success - Billing transfer invitation %s has been accepted",
                context.order_id,
                transfer_id,
            )
            responsibility_arn = transfer_details.get("ResponsibilityTransfer", {}).get("Arn")
            billing_group = context.aws_client.create_billing_group(
                responsibility_transfer_arn=responsibility_arn,
                pricing_plan_arn=BASIC_PRICING_PLAN_ARN,
                name=f"billing-group-{get_mpa_account_id(context.order)}",
                description=f"Billing group for MPA {get_mpa_account_id(context.order)}",
            )
            logger.info(
                "%s - Success - Billing group %s created for responsibility transfer %s",
                context.order_id,
                billing_group["Arn"],
                transfer_id,
            )
            context.order = set_billing_group_arn(context.order, billing_group["Arn"])
        elif status in INVALID_RESPONSIBILITY_TRANSFER_STATUS:
            raise FailStepError(
                "INVALID_RESPONSIBILITY_TRANSFER_STATUS",
                f"Billing transfer invitation {transfer_id} has status: {status}",
            )
        else:
            raise QueryStepError(
                f"Billing transfer invitation {transfer_id} is still pending",
                OrderQueryingTemplateEnum.TRANSFER_AWAITING_INVITATIONS,
            )

    @override
    def post_step(self, client: MPTClient, context: PurchaseContext) -> None:
        """Hook to run after the step processing."""
        context.order = set_phase(context.order, PhasesEnum.CONFIGURE_APN_PROGRAM)
        context.order = update_order(
            client, context.order_id, parameters=context.order["parameters"]
        )
