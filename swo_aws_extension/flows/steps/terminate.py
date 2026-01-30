import datetime as dt
import logging
from typing import override

from dateutil.relativedelta import relativedelta
from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.aws.errors import AWSError, InvalidDateInTerminateResponsibilityError
from swo_aws_extension.constants import (
    ChannelHandshakeDeployed,
    ExpirationPeriodEnum,
    ResponsibilityTransferStatus,
)
from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.errors import (
    FailStepError,
    SkipStepError,
    UnexpectedStopError,
)
from swo_aws_extension.parameters import (
    get_channel_handshake_approval_status,
    get_responsibility_transfer_id,
)

logger = logging.getLogger(__name__)

MINIMUM_DAYS_MONTH = 28


class TerminateResponsibilityTransferStep(BasePhaseStep):  # noqa: WPS214
    """Handles the termination of responsibility transfer."""

    def __init__(self, config) -> None:
        self._config = config

    @override
    def pre_step(self, context: InitialAWSContext) -> None:
        """Performs the preliminary step."""
        responsibility_transfer_id = get_responsibility_transfer_id(context.order)
        if not responsibility_transfer_id:
            raise SkipStepError(
                f"{context.order_id} - Responsibility transfer ID is missing in the order. "
                f"Completing the termination order."
            )

    @override
    def process(self, client: MPTClient, context: InitialAWSContext) -> None:
        """Terminates a responsibility transfer operation."""
        responsibility_transfer_id = get_responsibility_transfer_id(context.order)

        responsibility_transfer = context.aws_client.get_responsibility_transfer_details(
            responsibility_transfer_id,
        )
        status = responsibility_transfer.get("ResponsibilityTransfer", {}).get("Status")
        if status != ResponsibilityTransferStatus.ACCEPTED:
            logger.info(
                "%s - Skipping termination as transfer status is %s", context.order_id, status
            )
            return
        logger.info(
            "%s - Terminating responsibility transfer %s ",
            context.order_id,
            responsibility_transfer_id,
        )

        self.terminate_relationship_transfer(context, responsibility_transfer_id)

    def terminate_relationship_transfer(
        self, context: InitialAWSContext, responsibility_transfer_id
    ):
        """Terminates the responsibility transfer."""
        handshake_approved = (
            get_channel_handshake_approval_status(context.order) == ChannelHandshakeDeployed.YES
        )
        end_timestamp = self._get_responsibility_transfer_end_timestamp(
            handshake_approved=handshake_approved
        )
        try:
            context.aws_client.terminate_responsibility_transfer(
                responsibility_transfer_id, end_timestamp=end_timestamp
            )
        except InvalidDateInTerminateResponsibilityError as exception:
            raise FailStepError(
                "INVALID_END_DATE",
                f"Order failed due to invalid date in terminate responsibility agreement"
                f" with reason: {exception.message}",
            ) from exception

        except AWSError as exception:
            logger.info(
                "%s - Failed to terminate responsibility transfer with error: %s",
                context.order_id,
                exception,
            )
            raise UnexpectedStopError(
                title="Terminate responsibility transfer",
                message=(
                    f"{context.order_id} - unhandled exception while terminating"
                    f" responsibility transfer."
                ),
            ) from exception

    @override
    def post_step(self, client: MPTClient, context: InitialAWSContext) -> None:
        """Executes actions after a particular step in the process."""
        logger.info("%s - responsibility transfer completed successfully", context.order_id)

    def _get_responsibility_transfer_end_timestamp(
        self, *, handshake_approved: bool
    ) -> dt.datetime:
        now = dt.datetime.now(dt.UTC)

        delta = (
            relativedelta(months=ExpirationPeriodEnum.NEXT_MONTH)
            if handshake_approved
            else relativedelta(months=ExpirationPeriodEnum.CURRENT_MONTH)
        )

        target_month = now + delta
        first_day_month = target_month.replace(
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        return first_day_month - dt.timedelta(milliseconds=1)
