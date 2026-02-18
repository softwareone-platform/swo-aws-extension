import logging

from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.config import get_config
from swo_aws_extension.constants import (
    PhasesEnum,
    ResponsibilityTransferStatus,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.order_utils import switch_order_status_to_process_and_notify
from swo_aws_extension.parameters import get_responsibility_transfer_id
from swo_aws_extension.processors.processor import Processor
from swo_aws_extension.processors.querying.helper import get_template_name
from swo_aws_extension.swo.notifications.teams import (
    notify_one_time_error,
)

logger = logging.getLogger(__name__)


class AWSBillingTransferInvitationProcessor(Processor):
    """Process AWS billing transfer invitation."""

    def __init__(self, client: MPTClient):
        self.client = client

    def can_process(self, context: PurchaseContext) -> bool:
        """Check if the context is in checking billing transfer invitation phase."""
        return context.phase == PhasesEnum.CHECK_BILLING_TRANSFER_INVITATION

    def process(self, context: PurchaseContext) -> None:
        """Process AWS billing transfer invitation."""
        transfer_id = get_responsibility_transfer_id(context.order)
        if not transfer_id:
            logger.info(
                "%s - Skipping AWS pending invitation because transfer ID is missing.",
                context.order_id,
            )
            return
        if not context.pm_account_id:
            logger.info(
                "%s - Skipping AWS pending invitation because AWS PMA account ID is missing.",
                context.order_id,
            )
            return
        config = get_config()  # type: ignore[no-untyped-call]
        context.aws_client = AWSClient(config, context.pm_account_id, config.management_role_name)
        self.process_invitation(context, transfer_id)

    def process_invitation(self, context: PurchaseContext, transfer_id: str):
        """Process billing transfer invitation."""
        try:
            transfer_details = context.aws_client.get_responsibility_transfer_details(
                transfer_id=transfer_id
            )
        except AWSError as error:
            logger.info(
                "%s - Error - Failed to get billing transfer invitation %s details: %s",
                context.order_id,
                transfer_id,
                error,
            )
            notify_one_time_error(
                "Error processing AWS billing transfer invitations",
                f"{context.order_id} - Error getting billing transfer invitation "
                f"{transfer_id} details: {error!s}",
            )
            return

        status = transfer_details.get("ResponsibilityTransfer", {}).get("Status")

        if status != ResponsibilityTransferStatus.REQUESTED:
            logger.info(
                "%s - Action - Billing transfer invitation %s has changed status "
                "to %s. Moving order to processing.",
                context.order_id,
                transfer_id,
                status,
            )
            switch_order_status_to_process_and_notify(
                self.client, context, get_template_name(context)
            )
            return

        logger.info(
            "%s - Skip - Billing transfer invitation %s is still in REQUESTED status. "
            "Will check again later.",
            context.order_id,
            transfer_id,
        )
