import logging
from typing import Any

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.wrap_http_error import ValidationError

from swo_aws_extension.flows.fulfillment.pipelines import (
    pipeline_error_handler,
    purchase_existing_aws_environment,
    purchase_new_aws_environment,
    terminate,
)
from swo_aws_extension.flows.order import InitialAWSContext, PurchaseContext
from swo_aws_extension.flows.order_utils import switch_order_status_to_failed

logger = logging.getLogger(__name__)


def _handle_purchase_order(client: MPTClient, context: InitialAWSContext) -> None:
    purchase_context = PurchaseContext.from_context(context)
    if purchase_context.is_type_new_aws_environment():
        logger.info(
            "%s - Pipeline - Starting: purchase new AWS environment",
            purchase_context.order_id,
        )
        purchase_new_aws_environment.run(
            client, purchase_context, error_handler=pipeline_error_handler
        )
    elif purchase_context.is_type_existing_aws_environment():
        logger.info(
            "%s - Pipeline - Starting: purchase existing AWS environment",
            purchase_context.order_id,
        )
        purchase_existing_aws_environment.run(
            client, purchase_context, error_handler=pipeline_error_handler
        )


def _fail_unsupported_order(client: MPTClient, context: InitialAWSContext) -> None:
    logger.error(
        "%s - Order type %s is not supported, failing order",
        context.order_id,
        context.order_type,
    )
    switch_order_status_to_failed(
        client,
        context,
        ValidationError(
            err_id="AWS003",
            message=f"Order type {context.order_type} is not supported by the AWS extension.",
        ).to_dict(),
    )


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
        _handle_purchase_order(client, context)
    else:
        _fail_unsupported_order(client, context)


def setup_contexts(_: MPTClient, orders: list[dict[str, Any]]) -> list[InitialAWSContext]:
    """Sets up initial AWS contexts from order data."""
    return [InitialAWSContext.from_order_data(order) for order in orders]
