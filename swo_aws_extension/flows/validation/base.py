import logging
import traceback

from swo_aws_extension.flows.error import (
    strip_trace_id,
)
from swo_aws_extension.flows.order import (
    is_change_order,
    is_purchase_order,
    is_termination_order,
)
from swo_aws_extension.notifications import notify_unhandled_exception_in_teams

logger = logging.getLogger(__name__)


def validate_order(client, order):
    """
    Performs the validation of a draft order.

    Args:
        mpt_client (MPTClient): The client used to consume the MPT API.
        order (dict): The order to validate

    Returns:
        dict: The validated order.
    """
    try:
        has_errors = False

        if is_purchase_order(order):
            pass
        elif is_change_order(order):
            pass
        elif is_termination_order(order):
            pass

        logger.info(
            f"Validation of order {order['id']} succeeded "
            f"with{'out' if not has_errors else ''} errors"
        )
        return order
    except Exception:
        notify_unhandled_exception_in_teams(
            "validation",
            order["id"],
            strip_trace_id(traceback.format_exc()),
        )
        raise
