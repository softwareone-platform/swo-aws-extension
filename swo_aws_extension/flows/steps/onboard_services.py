import logging
from typing import override

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.config import Config
from swo_aws_extension.constants import (
    PhasesEnum,
)
from swo_aws_extension.flows.cloud_orchestrator_utils import (
    get_feature_version_onboard_request,
    onboard,
)
from swo_aws_extension.flows.flow_utils import handle_error
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.errors import SkipStepError
from swo_aws_extension.parameters import (
    get_phase,
    set_execution_arn,
    set_phase,
)
from swo_aws_extension.swo.cloud_orchestrator.errors import CloudOrchestratorError

logger = logging.getLogger(__name__)


class OnboardServices(BasePhaseStep):
    """Onboard Services step."""

    def __init__(self, config: Config) -> None:
        self._config = config

    @override
    def pre_step(self, context: PurchaseContext) -> None:
        phase = get_phase(context.order)
        if phase != PhasesEnum.ONBOARD_SERVICES:
            raise SkipStepError(
                f"{context.order_id} - Next - Current phase is '{phase}', skipping as it"
                f" is not '{PhasesEnum.ONBOARD_SERVICES}'"
            )

    @override
    def process(self, client: MPTClient, context: PurchaseContext) -> None:
        logger.info("%s - Action - Onboarding services", context.order_id)

        feature_version_payload = get_feature_version_onboard_request(context)

        error_email_log_message = "Onboarding services error email sent"

        is_error_occurred = False
        error_title = ""
        error_details = ""

        try:
            execution_arn = onboard(self._config, feature_version_payload, context.order_id)
        except CloudOrchestratorError as error:
            logger.exception("%s - CloudOrchestratorError", context.order_id)
            is_error_occurred = True
            error_title = (
                "Error deploying onboarding feature version and getting execution ARN for "
                f"order {context.order_id}"
            )
            error_details = (
                f"Error deploying onboarding feature version and getting execution ARN for "
                f"order {context.order_id}: {error}\n\n"
                f"for request payload:\n\n{feature_version_payload}"
            )
        else:
            if execution_arn:
                logger.info(
                    "%s - Next - Onboarding services started with execution ARN %s",
                    context.order_id,
                    execution_arn,
                )
                context.order = set_execution_arn(context.order, execution_arn)
            else:
                is_error_occurred = True
                error_title = (
                    "Error deploying onboarding feature version and getting execution ARN for "
                    f"order {context.order_id}"
                )
                error_details = (
                    f"No execution ARN returned for order {context.order_id} "
                    f"for request payload:\n\n{feature_version_payload}"
                )

        if is_error_occurred:
            handle_error(
                context,
                self._config,
                client,
                error_title,
                error_details,
                error_email_log_message,
            )
        else:
            update_order(client, context.order_id, parameters=context.order["parameters"])

    @override
    def post_step(self, client: MPTClient, context: PurchaseContext) -> None:
        context.order = set_phase(context.order, PhasesEnum.CHECK_ONBOARD_STATUS)
        context.order = update_order(
            client, context.order_id, parameters=context.order["parameters"]
        )
