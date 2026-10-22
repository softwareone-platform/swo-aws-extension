import logging
from typing import override

from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.cloud_orchestrator_utils import get_buyer_scu
from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.order_utils import has_previous_order
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.errors import FailStepError, SkipStepError, UnexpectedStopError
from swo_aws_extension.parameters import get_phase
from swo_aws_extension.swo.cloud_orchestrator.errors import CloudOrchestratorMissingScuError

logger = logging.getLogger(__name__)


class ValidateOrder(BasePhaseStep):
    """Validate purchase order before processing."""

    @override
    def pre_step(self, context: InitialAWSContext) -> None:
        logger.debug("%s - ValidateOrder - starting order validation", context.order_id)
        phase = get_phase(context.order)
        if phase != PhasesEnum.CREATE_BILLING_TRANSFER_INVITATION:
            raise SkipStepError(
                f"{context.order_id} - Next - Skip order validation",
            )

    @override
    def process(self, client: MPTClient, context: InitialAWSContext) -> None:
        if has_previous_order(client, context.order, context.agreement.get("id")):
            logger.warning(
                "%s - Duplicate agreement found for licensee %s, failing order",
                context.order_id,
                context.order.get("licensee", {}).get("id"),
            )
            raise FailStepError(
                "AWS004",
                "An active agreement already exists for this licensee. "
                "A new agreement can only be created with a different licensee.",
            )
        try:
            get_buyer_scu(context)
        except CloudOrchestratorMissingScuError as error:
            logger.warning("%s - %s", context.order_id, error)
            raise UnexpectedStopError(
                f"Buyer SCU is not set for order {context.order_id}", str(error)
            ) from error

    @override
    def post_step(self, client: MPTClient, context: InitialAWSContext) -> None:
        logger.info("%s - Next - ValidateOrder completed successfully", context.order_id)
