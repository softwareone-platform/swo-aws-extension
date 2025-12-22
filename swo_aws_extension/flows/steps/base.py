import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from mpt_extension_sdk.flows.pipeline import Step
from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.steps.errors import (
    ConfigurationStepError,
    UnexpectedStopError,
)
from swo_aws_extension.notifications import TeamsNotificationManager

logger = logging.getLogger(__name__)


class BasePhaseStep(Step, ABC):
    """Base class for all steps in the AWS provisioning flow."""

    def __call__(
        self,
        client: MPTClient,
        context: InitialAWSContext,
        next_step: Callable[[MPTClient, InitialAWSContext], Any],
    ) -> None:
        """Execute the step."""
        self._client = client
        self._next_step = next_step

        try:
            self.pre_step(context)
        except ConfigurationStepError as error:
            logger.info(
                "%s - Stop - Stop step due to configuration error: %s",
                context.order_id,
                error,
            )
            return

        try:
            self.process(context)
        except UnexpectedStopError as error:
            logger.info("%s - Unexpected Stop: %s", context.order_id, error)
            TeamsNotificationManager().notify_one_time_error(error.title, error.message)
            return

        self.post_step(context)
        self._next_step(self._client, context)

    @abstractmethod
    def process(self, context: InitialAWSContext) -> None:
        """Execute the actual step logic."""
        raise NotImplementedError

    @abstractmethod
    def pre_step(self, context: InitialAWSContext) -> None:
        """Hook to run before the step processing."""
        raise NotImplementedError

    @abstractmethod
    def post_step(self, context: InitialAWSContext) -> None:
        """Hook to run after the step processing."""
        raise NotImplementedError
