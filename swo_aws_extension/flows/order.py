import copy
from dataclasses import dataclass

from swo.mpt.client.mpt import get_product_template_or_default, query_order
from swo.mpt.extensions.flows.context import Context as BaseContext

from swo_aws_extension.aws.client import AccountCreationStatus, AWSClient
from swo_aws_extension.notifications import send_email_notification

MPT_ORDER_STATUS_PROCESSING = "Processing"
MPT_ORDER_STATUS_QUERYING = "Querying"
MPT_ORDER_STATUS_COMPLETED = "Completed"

ORDER_TYPE_PURCHASE = "Purchase"
ORDER_TYPE_CHANGE = "Change"
ORDER_TYPE_TERMINATION = "Termination"


def is_purchase_order(order):
    """
    Check if the order is a real purchase order or a subscriptions transfer order.
    Args:
        order (dict): The order to check.

    Returns:
        bool: True if it is a real purchase order, False otherwise.
    """
    return order["type"] == ORDER_TYPE_PURCHASE


def is_change_order(order):
    return order["type"] == ORDER_TYPE_CHANGE


def is_termination_order(order):
    return order["type"] == ORDER_TYPE_TERMINATION


@dataclass
class OrderContext(BaseContext):
    order: dict
    validation_succeeded: bool = True
    type: str | None = None
    order_id: str | None = None
    product_id: str | None = None
    aws_client: AWSClient | None = None
    account_creation_status: AccountCreationStatus | None = None

    @staticmethod
    def from_order(order: dict) -> "OrderContext":
        return OrderContext(
            order=order, order_id=order["id"], product_id=order["product"]["id"]
        )


def switch_order_to_query(client, order, template_name=None):
    """
    Switches the status of an MPT order to 'query' and resetting due date and
    initiating a query order process.

    Args:
        client (MPTClient): An instance of the Marketplace platform client.
        order (dict): The MPT order to be switched to 'query' status.
        template_name: The name of the template to use, if None -> use default

    Returns:
        dict: The updated order.
    """
    template = get_product_template_or_default(
        client,
        order["product"]["id"],
        MPT_ORDER_STATUS_QUERYING,
        name=template_name,
    )
    kwargs = {
        "parameters": order["parameters"],
        "template": template,
    }
    if order.get("error"):
        kwargs["error"] = order["error"]

    agreement = order["agreement"]
    order = query_order(
        client,
        order["id"],
        **kwargs,
    )
    order["agreement"] = agreement
    send_email_notification(client, order)
    return order


def reset_order_error(order):
    """
    Reset the error field of an order

    Args:
        order: The order to reset the error field of

    Returns: The updated order

    """
    updated_order = copy.deepcopy(order)
    updated_order["error"] = None
    return updated_order
