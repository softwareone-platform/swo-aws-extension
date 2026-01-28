import logging
from typing import override

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.constants import (
    ChannelHandshakeDeployed,
    ChannelHandshakeStatusEnum,
    OrderQueryingTemplateEnum,
    PhasesEnum,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.errors import (
    ConfigurationStepError,
    QueryStepError,
    SkipStepError,
    UnexpectedStopError,
)
from swo_aws_extension.parameters import (
    get_channel_handshake_id,
    get_phase,
    get_relationship_id,
    set_channel_handshake_approved,
    set_phase,
)

logger = logging.getLogger(__name__)


class CheckChannelHandshakeStatus(BasePhaseStep):
    """Check Channel Handshake Status step."""

    def __init__(self, config):
        self._config = config

    @override
    def pre_step(self, context: PurchaseContext) -> None:
        phase = get_phase(context.order)
        if phase != PhasesEnum.CHECK_CHANNEL_HANDSHAKE_STATUS:
            raise SkipStepError(
                f"{context.order_id} - Next - Current phase is '{phase}', skipping as it"
                f" is not '{PhasesEnum.CHECK_CHANNEL_HANDSHAKE_STATUS}'"
            )
        if not get_channel_handshake_id(context.order):
            raise ConfigurationStepError(
                "Error checking channel handshake status",
                "Channel handshake ID is missing in the order.",
            )

    @override
    def process(self, client: MPTClient, context: PurchaseContext):
        logger.info("%s - Action - Checking channel handshake status", context.order_id)
        context.order = set_channel_handshake_approved(
            context.order, ChannelHandshakeDeployed.NO_DEPLOYED
        )
        relationship_id = get_relationship_id(context.order)
        handshakes = context.aws_apn_client.get_channel_handshakes_by_resource(relationship_id)
        handshake_id = get_channel_handshake_id(context.order)

        handshake = next(
            (hs for hs in handshakes if hs.get("id") == handshake_id),
            None,
        )

        if not handshake:
            logger.info(
                "%s - Error - Channel handshake %s not found",
                context.order_id,
                handshake_id,
            )
            raise UnexpectedStopError(
                "Channel handshake not found",
                f"Channel handshake"
                f" {handshake_id} does not exist for relationship {relationship_id}.",
            )

        if handshake.get("status") == ChannelHandshakeStatusEnum.ACCEPTED.value:
            logger.info(
                "%s - Next - Channel handshake %s is accepted",
                context.order_id,
                handshake_id,
            )
            context.order = set_channel_handshake_approved(
                context.order, ChannelHandshakeDeployed.YES
            )
            return
        if handshake.get("status") == ChannelHandshakeStatusEnum.PENDING.value:
            logger.info(
                "%s - Skip - Channel handshake %s has status: %s",
                context.order_id,
                handshake_id,
                handshake.get("status"),
            )
            raise QueryStepError(
                "Channel handshake pending acceptance",
                template_id=OrderQueryingTemplateEnum.HANDSHAKE_AWAITING_ACCEPTANCE,
            )
        logger.info(
            "%s - Warning - Channel handshake %s is in status: %s. Should be managed manually.",
            context.order_id,
            handshake_id,
            handshake.get("status"),
        )

    @override
    def post_step(self, client: MPTClient, context: PurchaseContext) -> None:
        context.order = set_phase(context.order, PhasesEnum.CHECK_CUSTOMER_ROLES)
        context.order = update_order(
            client, context.order_id, parameters=context.order["parameters"]
        )
