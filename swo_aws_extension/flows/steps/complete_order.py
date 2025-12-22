import logging
from typing import override

from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.constants import OrderCompletedTemplate
from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.order_utils import switch_order_status_to_complete
from swo_aws_extension.flows.steps.base import BasePhaseStep

logger = logging.getLogger(__name__)


class CompleteTerminationOrder(BasePhaseStep):
    """Handles the completion of an order."""

    @override
    def pre_step(self, context: InitialAWSContext) -> None:
        logger.info("%s - Next - Starting Terminate order completion step", context.order_id)

    @override
    def process(self, client: MPTClient, context: InitialAWSContext) -> None:
        if context.is_type_new_aws_environment():
            template = OrderCompletedTemplate.TERMINATION_NEW_ACCOUNT
        else:
            template = OrderCompletedTemplate.TERMINATION_EXISTING_ACCOUNT

        switch_order_status_to_complete(client, context, template)

    @override
    def post_step(self, client: MPTClient, context: InitialAWSContext) -> None:
        logger.info(
            "%s - Completed - Termination order has been completed successfully", context.order_id
        )
