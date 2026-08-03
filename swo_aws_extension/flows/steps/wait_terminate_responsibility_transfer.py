import datetime as dt
import logging
from typing import override

from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.errors import ScheduleStepError, SkipStepError

logger = logging.getLogger(__name__)


class WaitTerminateResponsibilityTransferStep(BasePhaseStep):
    """Keeps the termination order processing until the transfer end date is reached."""

    def __init__(self, config) -> None:
        self._config = config

    @override
    def pre_step(self, context: InitialAWSContext) -> None:
        """Performs the preliminary step."""
        if not context.termination_effective_date:
            raise SkipStepError(
                f"{context.order_id} - No responsibility transfer end date to wait for. "
                f"Continuing with the termination order."
            )

    @override
    def process(self, client: MPTClient, context: InitialAWSContext) -> None:
        """Continues the termination once the responsibility transfer end date is reached."""
        end_date = context.termination_effective_date
        if end_date > dt.datetime.now(dt.UTC):
            raise ScheduleStepError(
                f"{context.order_id} - Wait - Responsibility transfer ends on {end_date}. "
                f"Keeping the order in processing until that date."
            )
        logger.info(
            "%s - Responsibility transfer end date %s reached. Continuing with the "
            "termination order.",
            context.order_id,
            end_date,
        )

    @override
    def post_step(self, client: MPTClient, context: InitialAWSContext) -> None:
        """Executes actions after a particular step in the process."""
        logger.info(
            "%s - Completed - responsibility transfer wait step completed",
            context.order_id,
        )
