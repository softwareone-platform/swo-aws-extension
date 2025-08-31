import logging
import traceback

from swo_aws_extension.airtable.models import get_available_mpa_from_pool
from swo_aws_extension.constants import TransferTypesEnum
from swo_aws_extension.flows.error import strip_trace_id
from swo_aws_extension.flows.fulfillment.pipelines import (
    change_order,
    purchase,
    purchase_split_billing,
    purchase_transfer_with_organization,
    purchase_transfer_without_organization,
    terminate,
)
from swo_aws_extension.flows.order import (
    ChangeContext,
    InitialAWSContext,
    PurchaseContext,
    TerminateContext,
    is_partner_led_support_enabled,
)
from swo_aws_extension.notifications import notify_unhandled_exception_in_teams
from swo_aws_extension.parameters import get_transfer_type

logger = logging.getLogger(__name__)


def fulfill_order(client, context):  # noqa: C901
    """
    Fulfills an order of any type by processing the necessary actions based on the parameters.

    Args:
        client (MPTClient): An instance of the client for consuming the MPT platform API.
        context (InitialAWSContext): The context of the order.

    Returns:
        None
    """
    logger.info("%s - Start processing %s", context.order_id, context.order_type)
    try:
        if context.is_purchase_order():
            context = PurchaseContext.from_context(context)  # type: PurchaseContext
            logger.info("Context type: %s %s", type(context), context)
            if context.is_type_transfer_with_organization():
                logger.info(
                    "%s - Pipeline - Starting: purchase transfer with organization",
                    context.order_id,
                )
                purchase_transfer_with_organization.run(client, context)
                return

            if context.is_type_transfer_without_organization():
                logger.info(
                    "%s - Pipeline - Starting: purchase transfer without organization",
                    context.order_id,
                )
                purchase_transfer_without_organization.run(client, context)
            elif context.is_split_billing():
                logger.info(
                    "%s - Pipeline - Starting: purchase split billing order", context.order_id,
                )
                purchase_split_billing.run(client, context)
            else:
                logger.info("%s - Pipeline - Starting: purchase", context.order_id)
                purchase.run(client, context)
        elif context.is_change_order():
            logger.info("%s - Pipeline - Starting: change order", context.order_id)
            context = ChangeContext.from_context(context)
            change_order.run(client, context)
        elif context.is_termination_order():  # pragma: no branch
            context = TerminateContext.from_context(context)
            terminate.run(client, context)
        else:
            logger.error("%s - Unsupported order type: %s", context.order_id, context.order_type)
    except Exception:
        notify_unhandled_exception_in_teams(
            "fulfillment",
            context.order_id,
            strip_trace_id(traceback.format_exc()),
        )
        raise


def get_mpa_by_country_and_pls(mpa_pool, country, pls):
    """
    Get list of MPA by country and PLS status for the provided MPA pool.

    Args:
        mpa_pool (list): List of MPAs
        country (str): Country code
        pls (bool): PLS status

    Returns: List of MPAs
    """
    return [mpa for mpa in mpa_pool if mpa.country == country and mpa.pls_enabled == pls]


def setup_contexts(mpt_client, orders):
    """
    List of contexts from orders.

    Args:
        mpt_client (MPTClient): MPT client
        orders (list): List of orders

    Returns: List of contexts
    """
    purchase_orders_pls_status_map = {
        order["id"]: (order["seller"]["address"]["country"], is_partner_led_support_enabled(order))
        for order in orders
        if not order.get("agreement", {}).get("externalIds", {}).get("vendor", "")
        and get_transfer_type(order)
        not in {
            TransferTypesEnum.TRANSFER_WITH_ORGANIZATION,
            TransferTypesEnum.SPLIT_BILLING,
        }
    }
    pls_mpa_pool_map = {}
    if purchase_orders_pls_status_map:
        mpa_pool = get_available_mpa_from_pool()
        pls_mpa_pool_map = {
            f"{country}_{pls}": get_mpa_by_country_and_pls(mpa_pool, country, pls)
            for country, pls in set(purchase_orders_pls_status_map.values())
        }

    contexts = []

    for order in orders:
        context = InitialAWSContext.from_order_data(order)
        if context.is_purchase_order() and order["id"] in purchase_orders_pls_status_map:
            country, pls = purchase_orders_pls_status_map[order["id"]]
            # Check if there is an available MPA for the order.
            # If there is, assign it to the context.
            # Otherwise, leave it as None to be handled on the order processed.
            if pls_mpa_pool_map.get(f"{country}_{pls}", None):
                # Assign first available MPA from the pool
                context.airtable_mpa = pls_mpa_pool_map[f"{country}_{pls}"].pop(0)

        contexts.append(context)

    return contexts
