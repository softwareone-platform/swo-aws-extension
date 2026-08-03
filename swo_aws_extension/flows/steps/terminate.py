import datetime as dt
import logging
from typing import override

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.aws.errors import (
    AWSError,
    InvalidDateInTerminateResponsibilityError,
)
from swo_aws_extension.constants import (
    CHANNEL_HANDSHAKE_MINIMUM_NOTICE_DAYS,
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
    get_relationship_end_date,
    get_responsibility_transfer_id,
    set_relationship_end_date,
)
from swo_aws_extension.utils import date_parser

logger = logging.getLogger(__name__)


class TerminateResponsibilityTransferStep(BasePhaseStep):
    """Schedules the withdrawal of the responsibility transfer."""

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
        saved_end_date = get_relationship_end_date(context.order)
        if saved_end_date:
            context.termination_effective_date = date_parser.to_utc(
                dt.datetime.fromisoformat(saved_end_date)
            )
            raise SkipStepError(
                f"{context.order_id} - Next - Responsibility transfer end date already "
                f"known: {saved_end_date}. "
            )

    @override
    def process(self, client: MPTClient, context: InitialAWSContext) -> None:
        """Schedules the withdrawal of the responsibility transfer."""
        responsibility_transfer_id = get_responsibility_transfer_id(context.order)

        responsibility_transfer = context.aws_client.get_responsibility_transfer_details(
            responsibility_transfer_id,
        ).get("ResponsibilityTransfer", {})
        status = responsibility_transfer.get("Status")
        scheduled_end = responsibility_transfer.get("EndTimestamp")

        if scheduled_end:
            self._set_relationship_end_date(context, scheduled_end)
            logger.info(
                "%s - Responsibility transfer %s already has an end date configured: %s",
                context.order_id,
                responsibility_transfer_id,
                scheduled_end,
            )
            return

        if status != ResponsibilityTransferStatus.ACCEPTED:
            logger.info(
                "%s - Skipping termination as transfer status is %s",
                context.order_id,
                status,
            )
            return

        scheduled_end = date_parser.end_of_month(
            dt.datetime.now(dt.UTC) + dt.timedelta(days=CHANNEL_HANDSHAKE_MINIMUM_NOTICE_DAYS)
        )
        logger.info(
            "%s - Terminating responsibility transfer %s with end date %s to honor the "
            "%s days notice period",
            context.order_id,
            responsibility_transfer_id,
            scheduled_end,
            CHANNEL_HANDSHAKE_MINIMUM_NOTICE_DAYS,
        )
        self._terminate_relationship_transfer(context, responsibility_transfer_id, scheduled_end)
        self._set_relationship_end_date(context, scheduled_end)

    @override
    def post_step(self, client: MPTClient, context: InitialAWSContext) -> None:
        """Persists the fulfillment parameters after the step processing."""
        context.order = update_order(
            client, context.order_id, parameters=context.order["parameters"]
        )
        logger.info(
            "%s - Completed - responsibility transfer termination step completed",
            context.order_id,
        )

    def _set_relationship_end_date(self, context: InitialAWSContext, end_date: dt.datetime) -> None:
        end_date = date_parser.to_utc(end_date)
        context.termination_effective_date = end_date
        context.order = set_relationship_end_date(context.order, end_date.isoformat())

    def _terminate_relationship_transfer(
        self,
        context: InitialAWSContext,
        responsibility_transfer_id,
        end_timestamp: dt.datetime,
    ):
        try:
            context.aws_client.terminate_responsibility_transfer(
                responsibility_transfer_id,
                end_timestamp=end_timestamp,
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
