import logging
import traceback

from swo_aws_extension.flows.error import strip_trace_id
from swo_aws_extension.flows.fulfillment.pipelines import (
    change_order,
    purchase,
    terminate,
)
from swo_aws_extension.flows.order import (
    OrderContext,
    TerminateContext,
    is_change_order,
    is_purchase_order,
    is_termination_order,
)
from swo_aws_extension.notifications import notify_unhandled_exception_in_teams

logger = logging.getLogger(__name__)


def fulfill_order(
    client,
    order,
):
    """
    Fulfills an order of any type by processing the necessary actions
    based on the provided parameters.

    Args:
        client (MPTClient): An instance of the client for consuming the MPT platform API.
        order (dict): The order that needs to be processed.

    Returns:
        None
    """
    logger.info(f'Start processing {order["type"]} order {order["id"]}')
    context = OrderContext.from_order(order)
    try:
        if is_purchase_order(order):
            purchase.run(client, context)
        elif is_change_order(order):
            logger.info("Processing change order")
            change_order.run(client, context)
        elif is_termination_order(order):  # pragma: no branch
            context = TerminateContext.from_order(order)
            terminate.run(client, context)
        else:
            logger.warning(f"Unsupported order type: {order['type']}")
    except Exception:
        notify_unhandled_exception_in_teams(
            "fulfillment",
            order["id"],
            strip_trace_id(traceback.format_exc()),
        )
        raise
