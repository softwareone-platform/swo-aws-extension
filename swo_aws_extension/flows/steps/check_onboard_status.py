import logging
from typing import override

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.config import Config
from swo_aws_extension.constants import DeploymentStatusEnum, PhasesEnum
from swo_aws_extension.flows.cloud_orchestrator_utils import check_onboard_status
from swo_aws_extension.flows.flow_utils import handle_error
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.errors import SkipStepError
from swo_aws_extension.parameters import get_execution_arn, get_phase, set_phase
from swo_aws_extension.swo.cloud_orchestrator.errors import CloudOrchestratorError

logger = logging.getLogger(__name__)


class CheckOnboardStatus(BasePhaseStep):
    """Check Onboard Status step."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._onboard_still_running = False

    @override
    def pre_step(self, context: PurchaseContext) -> None:
        phase = get_phase(context.order)
        if phase != PhasesEnum.CHECK_ONBOARD_STATUS:
            raise SkipStepError(
                f"{context.order_id} - Next - Current phase is '{phase}', skipping as it"
                f" is not '{PhasesEnum.CHECK_ONBOARD_STATUS}'"
            )

    @override
    def process(self, client: MPTClient, context: PurchaseContext) -> None:
        logger.info("%s - Next - Checking onboard status", context.order_id)

        error_email_log_message = "Onboard status check error email sent"
        error_title = "Error checking onboard status"
        self._onboard_still_running = False

        execution_arn_value = get_execution_arn(context.order)
        if not execution_arn_value:
            handle_error(
                context,
                self._config,
                client,
                error_title,
                f"No execution ARN found on order {context.order_id} when checking onboard status",
                error_email_log_message,
            )
            return

        try:
            onboard_status_value = check_onboard_status(self._config, context, execution_arn_value)
        except CloudOrchestratorError as error:
            logger.exception("%s - CloudOrchestratorError", context.order_id)
            handle_error(
                context,
                self._config,
                client,
                error_title,
                f"Error checking onboard status for order {context.order_id}: {error}",
                error_email_log_message,
            )
            return

        if onboard_status_value in {
            DeploymentStatusEnum.RUNNING.value,
            DeploymentStatusEnum.PENDING.value,
        }:
            logger.info("%s - Next - Onboard status %s", context.order_id, onboard_status_value)
            self._onboard_still_running = True
            return

        if onboard_status_value == DeploymentStatusEnum.FAILED.value:
            handle_error(
                context,
                self._config,
                client,
                error_title,
                f"Onboard process failed in Cloud Orchestrator for order {context.order_id}",
                error_email_log_message,
            )
            return

        if onboard_status_value != DeploymentStatusEnum.SUCCEEDED.value:
            logger.warning(
                "%s - Next - Unexpected onboard status: %s",
                context.order_id,
                onboard_status_value,
            )
            self._onboard_still_running = True
            return

        logger.info("%s - Next - Onboard status check completed successfully", context.order_id)

    @override
    def post_step(self, client: MPTClient, context: PurchaseContext) -> None:
        if self._onboard_still_running:
            return
        context.order = set_phase(context.order, PhasesEnum.CREATE_SUBSCRIPTION)
        context.order = update_order(
            client, context.order_id, parameters=context.order["parameters"]
        )
