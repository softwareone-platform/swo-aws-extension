import logging

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.config import Config
from swo_aws_extension.constants import (
    ChannelHandshakeStatusEnum,
    OrderProcessingTemplateEnum,
    PhasesEnum,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.order_utils import switch_order_status_to_process_and_notify
from swo_aws_extension.parameters import (
    get_channel_handshake_id,
    get_relationship_id,
    set_phase,
)
from swo_aws_extension.processors.processor import Processor
from swo_aws_extension.processors.querying.helper import get_template_name, is_querying_timeout

logger = logging.getLogger(__name__)


class AWSChannelHandshakeProcessor(Processor):
    """Process AWS channel handshake timeout."""

    def __init__(self, client: MPTClient, config: Config):
        self.client = client
        self._config = config

    def can_process(self, context: PurchaseContext) -> bool:
        """Check if the order is in phase to check channel handshake status."""
        return context.phase == PhasesEnum.CHECK_CHANNEL_HANDSHAKE_STATUS

    def process(self, context: PurchaseContext) -> None:
        """Process AWS channel handshake timeout."""
        logger.info("%s - Checking channel handshake status.", context.order_id)

        self.setup_apn_client(context)

        relationship_id = get_relationship_id(context.order)
        handshake_id = get_channel_handshake_id(context.order)
        handshake = context.aws_apn_client.get_channel_handshake_by_id(
            relationship_id, handshake_id
        )

        if not handshake:
            logger.info(
                "%s - Error - Channel handshake %s not found",
                context.order_id,
                handshake_id,
            )
            switch_order_status_to_process_and_notify(
                self.client, context, OrderProcessingTemplateEnum.EXISTING_ACCOUNT
            )
            return

        if handshake.get("status") != ChannelHandshakeStatusEnum.PENDING.value:
            logger.info(
                "%s - Channel handshake %s is %s. Updating order to processing.",
                context.order_id,
                handshake_id,
                handshake.get("status"),
            )
            switch_order_status_to_process_and_notify(
                self.client, context, get_template_name(context)
            )
            return

        if is_querying_timeout(context, self._config.querying_timeout_days):
            self._manage_querying_timeout(context, handshake, handshake_id)
            return

        logger.info(
            "%s - Skip - Channel handshake %s is still in %s status and not timed out.",
            context.order_id,
            handshake_id,
            handshake.get("status"),
        )

    def setup_apn_client(self, context: PurchaseContext):
        """Setup AWS apn client in context."""
        apn_account_id = self._config.apn_account_id
        apn_role_name = self._config.apn_role_name
        context.aws_apn_client = AWSClient(self._config, apn_account_id, apn_role_name)

    def _manage_querying_timeout(
        self, context: PurchaseContext, handshake: dict, handshake_id: str | None
    ):
        logger.info(
            "%s - Handshake timeout - Channel handshake %s has status: %s.",
            context.order_id,
            handshake_id,
            handshake.get("status"),
        )
        logger.info(
            "%s - Updating order to processing with Phase CHECK_CUSTOMER_ROLES.",
            context.order_id,
        )
        context.order = set_phase(context.order, PhasesEnum.CHECK_CUSTOMER_ROLES)
        context.order = update_order(
            self.client, context.order_id, parameters=context.order["parameters"]
        )
        switch_order_status_to_process_and_notify(self.client, context, get_template_name(context))
