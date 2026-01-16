import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from mpt_extension_sdk.flows.pipeline import Step
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.flows.order import (
    InitialAWSContext,
)
from swo_aws_extension.flows.order_utils import (
    switch_order_status_to_failed_and_notify,
    switch_order_status_to_query_and_notify,
)
from swo_aws_extension.flows.steps.errors import (
    AlreadyProcessedStepError,
    ConfigurationStepError,
    FailStepError,
    QueryStepError,
    SkipStepError,
    UnexpectedStopError,
)
from swo_aws_extension.notifications import TeamsNotificationManager

logger = logging.getLogger(__name__)


class BasePhaseStep(Step, ABC):
    """Base class for all steps in the AWS provisioning flow."""

    def __call__(  # noqa: WPS213
        self,
        client: MPTClient,
        context: InitialAWSContext,
        next_step: Callable[[MPTClient, InitialAWSContext], Any],
    ) -> None:
        """Execute the step."""
        self._client = client
        self._next_step = next_step

        if not self._run_pre_step(context):
            return

        if not self._run_process(context):
            return

        self.post_step(self._client, context)
        self._next_step(self._client, context)

    @abstractmethod
    def process(self, client: MPTClient, context: InitialAWSContext) -> None:
        """Execute the actual step logic."""
        raise NotImplementedError

    @abstractmethod
    def pre_step(self, context: InitialAWSContext) -> None:
        """Hook to run before the step processing."""
        raise NotImplementedError

    @abstractmethod
    def post_step(self, client: MPTClient, context: InitialAWSContext) -> None:
        """Hook to run after the step processing."""
        raise NotImplementedError

    def _run_pre_step(self, context: InitialAWSContext) -> bool:
        try:
            self.pre_step(context)
        except AlreadyProcessedStepError as error:
            logger.info(str(error))
            context.order = update_order(
                self._client, context.order_id, parameters=context.order["parameters"]
            )
            self._next_step(self._client, context)
            return False
        except SkipStepError as error:
            logger.info(str(error))
            self._next_step(self._client, context)
            return False
        except ConfigurationStepError as error:
            logger.info(
                "%s - Stop - Stop step due to configuration error: %s",
                context.order_id,
                error,
            )
            TeamsNotificationManager().notify_one_time_error(error.title, error.message)
            return False
        return True

    def _run_process(self, context: InitialAWSContext) -> bool:
        try:
            self.process(self._client, context)
        except UnexpectedStopError as error:
            logger.info("%s - Unexpected Stop: %s", context.order_id, error)
            TeamsNotificationManager().notify_one_time_error(error.title, error.message)
            return False
        except QueryStepError as error:
            logger.info("%s - Query Order: %s", context.order_id, error.message)
            switch_order_status_to_query_and_notify(self._client, context, error.template_id)
            return False
        except FailStepError as error:
            logger.info("%s - Fail Order: %s", context.order_id, error)
            switch_order_status_to_failed_and_notify(self._client, context, str(error))
            return False
        return True
