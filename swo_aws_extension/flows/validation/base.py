import logging
import traceback

from swo_aws_extension.flows.error import (
    strip_trace_id,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.validation.change import validate_and_setup_change_order
from swo_aws_extension.flows.validation.purchase import validate_purchase_order
from swo_aws_extension.notifications import notify_unhandled_exception_in_teams

logger = logging.getLogger(__name__)


def validate_order(mpt_client, context):
    """
    Performs the validation of a draft order.

    Args:
        mpt_client (MPTClient): The client used to consume the MPT API.
        context (InitialAWSContext): The context of the order.

    Returns:
        dict: The validated order.
    """
    try:
        has_errors = False
        order = context.order
        if context.is_purchase_order():
            purchase_context = PurchaseContext.from_context(context)
            has_errors, order = validate_purchase_order(mpt_client, purchase_context)

        elif context.is_change_order():
            logger.info(f"agreement={context.agreement}")
            has_errors, order = validate_and_setup_change_order(mpt_client, context)
            logger.info(f"order={order}")
        elif context.is_termination_order():
            pass

        logger.info(
            f"Validation of order {context.order['id']} succeeded "
            f"with{'out' if not has_errors else ''} errors"
        )
        return order
    except Exception:
        notify_unhandled_exception_in_teams(
            "validation",
            context.order["id"],
            strip_trace_id(traceback.format_exc()),
        )
        raise
