import datetime as dt
import logging
from typing import override

from dateutil.relativedelta import relativedelta
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.errors import (
    AlreadyProcessedStepError,
    SkipStepError,
    UnexpectedStopError,
)
from swo_aws_extension.parameters import (
    get_channel_handshake_id,
    get_phase,
    get_relationship_id,
    set_channel_handshake_id,
    set_phase,
)

logger = logging.getLogger(__name__)


class CreateChannelHandshake(BasePhaseStep):
    """Handles the creation of a channel handshake."""

    def __init__(self, config):
        self._config = config

    @override
    def pre_step(self, context: PurchaseContext) -> None:
        phase = get_phase(context.order)
        if phase != PhasesEnum.CREATE_CHANNEL_HANDSHAKE:
            raise SkipStepError(
                f"{context.order_id} - Next - Current phase is '{phase}', skipping as it"
                f" is not '{PhasesEnum.CREATE_CHANNEL_HANDSHAKE}'"
            )
        if get_channel_handshake_id(context.order):
            context.order = set_phase(context.order, PhasesEnum.CHECK_CHANNEL_HANDSHAKE_STATUS)
            raise AlreadyProcessedStepError(
                f"{context.order_id} - Next - Channel handshake already created. Continue"
            )

    @override
    def process(self, client: MPTClient, context: PurchaseContext):
        logger.info(
            "%s - Action - Creating new channel handshake for 1 year period", context.order_id
        )
        pm_identifier = context.aws_apn_client.get_program_management_id_by_account(
            context.pm_account_id
        )

        now = dt.datetime.now(dt.UTC)
        first_of_next_month = (now.replace(day=1) + relativedelta(months=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        try:
            handshake = context.aws_apn_client.create_channel_handshake(
                pma_identifier=pm_identifier,
                note="Initial channel handshake",  # TODO pending note message from services
                relationship_identifier=get_relationship_id(context.order),
                end_date=first_of_next_month + relativedelta(years=1),
            )
        except AWSError as error:
            raise UnexpectedStopError(
                "Failed to create channel handshake",
                f"{context.order_id} - Failed to create channel handshake: {error}",
            ) from error

        context.order = set_channel_handshake_id(
            context.order, handshake["channelHandshakeDetail"]["id"]
        )
        logger.info(
            "%s - Success - Created channel handshake with ID %s",
            context.order_id,
            handshake["channelHandshakeDetail"]["id"],
        )

    @override
    def post_step(self, client: MPTClient, context: PurchaseContext) -> None:
        context.order = set_phase(context.order, PhasesEnum.CHECK_CHANNEL_HANDSHAKE_STATUS)
        context.order = update_order(
            client, context.order_id, parameters=context.order["parameters"]
        )
