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
from swo_aws_extension.swo.notifications.teams import notify_cloud_orchestrator_error

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

        try:
            execution_arn = onboard(self._config, feature_version_payload, context.order_id)
        except CloudOrchestratorError as error:
            logger.exception("%s - CloudOrchestratorError", context.order_id)
            notify_cloud_orchestrator_error(error, context.order_id)
            handle_error(
                context,
                self._config,
                client,
                (
                    "Error deploying onboarding feature version and getting execution ARN for "
                    f"order {context.order_id}"
                ),
                error.message,
                "Onboarding services error email sent",
            )
            return

        logger.info(
            "%s - Next - Onboarding services started with execution ARN %s",
            context.order_id,
            execution_arn,
        )
        context.order = set_execution_arn(context.order, execution_arn)
        update_order(client, context.order_id, parameters=context.order["parameters"])

    @override
    def post_step(self, client: MPTClient, context: PurchaseContext) -> None:
        context.order = set_phase(context.order, PhasesEnum.CHECK_ONBOARD_STATUS)
        context.order = update_order(
            client, context.order_id, parameters=context.order["parameters"]
        )
