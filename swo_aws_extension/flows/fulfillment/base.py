import logging
import re
import traceback
from typing import Any

from swo_aws_extension.flows.fulfillment.pipelines import (
    purchase_existing_aws_environment,
    purchase_new_aws_environment,
)
from swo_aws_extension.flows.order import InitialAWSContext, PurchaseContext
from swo_aws_extension.notifications import notify_unhandled_exception_in_teams

logger = logging.getLogger(__name__)


TRACE_ID_REGEX = re.compile(r"(\(00-[0-9a-f]{32}-[0-9a-f]{16}-01\))")


def strip_trace_id(traceback_msg: str) -> str:
    """Strip trace id."""
    return TRACE_ID_REGEX.sub("(<omitted>)", traceback_msg)


def fulfill_order(client: Any, context: InitialAWSContext) -> None:
    """
    Fulfills an order of any type by processing the necessary actions based on the parameters.

    Args:
        client: An instance of the client for consuming the MPT platform API.
        context: The context of the order.
    """
    logger.info("%s - Start processing %s", context.order_id, context.order_type)
    try:
        if context.is_purchase_order():
            context = PurchaseContext.from_context(context)
            if context.is_type_new_aws_environment():
                logger.info(
                    "%s - Pipeline - Starting: purchase new AWS environment",
                    context.order_id,
                )
                purchase_new_aws_environment.run(client, context)
                return
            if context.is_type_existing_aws_environment():
                logger.info(
                    "%s - Pipeline - Starting: purchase existing AWS environment",
                    context.order_id,
                )
                purchase_existing_aws_environment.run(client, context)
                return
        else:
            logger.error("%s - Unsupported order type: %s", context.order_id, context.order_type)
    except Exception:
        notify_unhandled_exception_in_teams(
            "fulfillment",
            context.order_id,
            strip_trace_id(traceback.format_exc()),
        )
        raise


def setup_contexts(_: Any, orders: list[dict[str, Any]]) -> list[InitialAWSContext]:
    """Sets up initial AWS contexts from order data."""
    return [InitialAWSContext.from_order_data(order) for order in orders]
