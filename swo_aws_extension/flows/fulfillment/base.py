import logging
from typing import Any

from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.flows.fulfillment.pipelines import (
    pipeline_error_handler,
    purchase_existing_aws_environment,
    purchase_new_aws_environment,
    terminate,
)
from swo_aws_extension.flows.order import InitialAWSContext, PurchaseContext

logger = logging.getLogger(__name__)


def fulfill_order(client: MPTClient, context: InitialAWSContext) -> None:
    """
    Fulfills an order of any type by processing the necessary actions based on the parameters.

    Args:
        client: An instance of the client for consuming the MPT platform API.
        context: The context of the order.
    """
    logger.info("%s - Start processing %s", context.order_id, context.order_type)

    if context.is_termination_order():
        terminate.run(client, context, error_handler=pipeline_error_handler)
    elif context.is_purchase_order():
        context = PurchaseContext.from_context(context)
        if context.is_type_new_aws_environment():
            logger.info(
                "%s - Pipeline - Starting: purchase new AWS environment",
                context.order_id,
            )
            purchase_new_aws_environment.run(client, context, error_handler=pipeline_error_handler)

        elif context.is_type_existing_aws_environment():
            logger.info(
                "%s - Pipeline - Starting: purchase existing AWS environment",
                context.order_id,
            )
            purchase_existing_aws_environment.run(
                client, context, error_handler=pipeline_error_handler
            )
    else:
        logger.error("%s - Unsupported order type: %s", context.order_id, context.order_type)


def setup_contexts(_: MPTClient, orders: list[dict[str, Any]]) -> list[InitialAWSContext]:
    """Sets up initial AWS contexts from order data."""
    return [InitialAWSContext.from_order_data(order) for order in orders]
