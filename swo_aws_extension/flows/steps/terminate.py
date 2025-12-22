import datetime as dt
import logging
from typing import override

from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.errors import ConfigurationStepError, UnexpectedStopError
from swo_aws_extension.parameters import get_responsibility_transfer_id

logger = logging.getLogger(__name__)


class TerminateResponsibilityTransferStep(BasePhaseStep):
    """Handles the termination of responsibility transfer."""

    @override
    def pre_step(self, context: InitialAWSContext) -> None:
        """Performs the preliminary step."""
        title = "Terminate responsibility transfer"
        if not context.agreement:
            raise ConfigurationStepError(
                title, "Agreement is required to assign transfer_id in context"
            )
        context.transfer_id = get_responsibility_transfer_id(context.agreement)
        if not context.transfer_id:
            raise ConfigurationStepError(title, "Transfer ID not found in the Agreement")

    @override
    def process(self, client: MPTClient, context: InitialAWSContext) -> None:
        """Terminates a responsibility transfer operation."""
        now = dt.datetime.now(tz=dt.UTC)
        it_is_december = now.month == 12  # noqa:WPS432
        end_timestamp = dt.datetime(
            year=now.year + 1 if it_is_december else now.year,
            month=1 if it_is_december else now.month + 1,
            day=1,
            tzinfo=dt.UTC,
        )

        logger.info("%s - Terminating responsibility transfer ", context.agreement)
        try:
            context.aws_client.terminate_responsibility_transfer(
                context.transfer_id, end_timestamp=end_timestamp
            )
        except Exception as exception:
            raise UnexpectedStopError(
                title="Terminate responsibility transfer",
                message=(
                    f"{context.agreement['id']} - unhandled exception while terminating"
                    f" responsibility transfer."
                ),
            ) from exception

    @override
    def post_step(self, client: MPTClient, context: InitialAWSContext) -> None:
        """Executes actions after a particular step in the process."""
        logger.info("%s - responsibility transfer completed successfully", context.agreement["id"])
