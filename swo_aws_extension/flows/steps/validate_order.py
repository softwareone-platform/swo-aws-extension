import logging
from typing import override

from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.order_utils import get_previous_order
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.errors import FailStepError

logger = logging.getLogger(__name__)


class ValidateOrder(BasePhaseStep):
    """Validate purchase order before processing."""

    @override
    def pre_step(self, context: InitialAWSContext) -> None:
        logger.debug("%s - ValidateOrder - starting order validation", context.order_id)

    @override
    def process(self, client: MPTClient, context: InitialAWSContext) -> None:
        if get_previous_order(client, context.order):
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

    @override
    def post_step(self, client: MPTClient, context: InitialAWSContext) -> None:
        logger.info("%s - Next - ValidateOrder completed successfully", context.order_id)
