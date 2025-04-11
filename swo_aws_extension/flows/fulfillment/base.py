import logging
import traceback

from swo_aws_extension.airtable.models import get_available_mpa_from_pool
from swo_aws_extension.constants import TransferTypesEnum
from swo_aws_extension.flows.error import strip_trace_id
from swo_aws_extension.flows.fulfillment.pipelines import (
    change_order,
    purchase,
    purchase_transfer_with_organization,
    purchase_transfer_without_organization,
    terminate,
)
from swo_aws_extension.flows.order import (
    InitialAWSContext,
    PurchaseContext,
    TerminateContext,
    is_partner_led_support_enabled,
)
from swo_aws_extension.notifications import notify_unhandled_exception_in_teams
from swo_aws_extension.parameters import get_transfer_type

logger = logging.getLogger(__name__)


def fulfill_order(client, context):
    """
    Fulfills an order of any type by processing the necessary actions
    based on the provided parameters.

    Args:
        client (MPTClient): An instance of the client for consuming the MPT platform API.
        context (InitialAWSContext): The context of the order.

    Returns:
        None
    """
    logger.info(f"Start processing {context.order_type} order {context.order_id}")
    try:
        if context.is_purchase_order():
            context = PurchaseContext.from_context(context)  # type: PurchaseContext
            logger.info(f"Context type: {type(context)} {context}")
            if context.is_type_transfer_with_organization():
                logger.info(
                    f"{context.order_id} - Pipeline - Starting: "
                    f"purchase_transfer_with_organization"
                )
                purchase_transfer_with_organization.run(client, context)
                return
            elif context.is_type_transfer_without_organization():
                logger.info(
                    f"{context.order_id} - Pipeline - Starting: "
                    f"purchase_transfer_without_organization"
                )
                purchase_transfer_without_organization.run(client, context)
            else:
                logger.info(f"{context.order_id} - Pipeline - Starting: purchase")
                purchase.run(client, context)
        elif context.is_change_order():
            logger.info("Processing change order")
            change_order.run(client, context)
        elif context.is_termination_order():  # pragma: no branch
            context = TerminateContext.from_context(context)
            terminate.run(client, context)
        else:
            logger.warning(f"Unsupported order type: {context.order_type}")
    except Exception:
        notify_unhandled_exception_in_teams(
            "fulfillment",
            context.order_id,
            strip_trace_id(traceback.format_exc()),
        )
        raise


def setup_contexts(mpt_client, orders):
    """
    List of contexts from orders
    Args:
        mpt_client (MPTClient): MPT client
        orders (list): List of orders

    Returns: List of contexts
    """
    purchase_orders_pls_status_map = {
        order["id"]: is_partner_led_support_enabled(order)
        for order in orders
        if not order.get("agreement", {}).get("externalIds", {}).get("vendor", "")
        and get_transfer_type(order)
        not in [
            TransferTypesEnum.TRANSFER_WITH_ORGANIZATION,
            TransferTypesEnum.SPLIT_BILLING,
        ]
    }
    pls_mpa_pool_map = {
        pls: get_available_mpa_from_pool(pls)
        for pls in set(purchase_orders_pls_status_map.values())
    }

    contexts = []

    for order in orders:
        context = InitialAWSContext(order=order)
        if context.is_purchase_order():
            if order["id"] in purchase_orders_pls_status_map:
                pls_status = purchase_orders_pls_status_map[order["id"]]
                # Check if there is an available MPA for the order.
                # If there is, assign it to the context.
                # Otherwise, leave it as None to be handled on the order processed.
                if pls_mpa_pool_map[pls_status]:
                    # Assign first available MPA from the pool
                    context.airtable_mpa = pls_mpa_pool_map[pls_status].pop(0)

        contexts.append(context)

    return contexts
