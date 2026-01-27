import datetime as dt
import logging
from typing import override

from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.aws.errors import AWSError, InvalidDateInTerminateResponsibilityError
from swo_aws_extension.constants import ResponsibilityTransferStatus
from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.errors import (
    FailStepError,
    SkipStepError,
    UnexpectedStopError,
)
from swo_aws_extension.parameters import get_billing_group_arn, get_responsibility_transfer_id

logger = logging.getLogger(__name__)

MINIMUM_DAYS_MONTH = 28


class TerminateResponsibilityTransferStep(BasePhaseStep):
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
        try:
            context.aws_client.terminate_responsibility_transfer(
                responsibility_transfer_id,
                end_timestamp=self._get_last_day_of_the_month_timestamp(),
            )
        except InvalidDateInTerminateResponsibilityError as exception:
            raise FailStepError(
                f"Order failed due to invalid date in terminate responsibility agreement"
                f" with reason: {exception.message}"
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

        billing_group_arn = get_billing_group_arn(context.order)
        try:
            context.aws_client.delete_billing_group(billing_group_arn)
        except AWSError as exception:
            logger.info(
                "%s - Failed to delete billing group with error: %s",
                context.order_id,
                exception,
            )
            return
        logger.info("%s - Billing group %s deleted", context.order_id, billing_group_arn)

    @override
    def post_step(self, client: MPTClient, context: InitialAWSContext) -> None:
        """Executes actions after a particular step in the process."""
        logger.info("%s - responsibility transfer completed successfully", context.order_id)

    def _get_last_day_of_the_month_timestamp(self) -> dt.datetime:
        # The end date must be the end of the last day of the month (23.59.59.999).

        now = dt.datetime.now(dt.UTC)

        first_day_next_month = (
            now.replace(day=MINIMUM_DAYS_MONTH, hour=0, minute=0, second=0, microsecond=0)
            + dt.timedelta(days=4)
        ).replace(day=1)

        return first_day_next_month - dt.timedelta(milliseconds=1)
