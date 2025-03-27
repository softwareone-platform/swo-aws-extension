import copy
from dataclasses import dataclass

from swo.mpt.client.mpt import get_product_template_or_default, query_order
from swo.mpt.extensions.flows.context import Context as BaseContext

from swo_aws_extension.aws.client import AccountCreationStatus, AWSClient
from swo_aws_extension.notifications import send_email_notification
from swo_aws_extension.parameters import (
    get_mpa_account_id,
)

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
    product_id: str | None = None
    aws_client: AWSClient | None = None
    account_creation_status: AccountCreationStatus | None = None

    @property
    def order_id(self):
        try:
            return self.order.get("id", None)
        except (AttributeError, KeyError):
            return None

    @property
    def order_type(self):
        return self.order.get("type", None)

    @classmethod
    def from_order(cls, order: dict) -> "OrderContext":
        return cls(order=order, product_id=order["product"]["id"])

    @property
    def mpa_account(self):
        try:
            return get_mpa_account_id(self.order)
        except (AttributeError, KeyError, TypeError):
            return None

    def __str__(self):
        return f"Context: {self.order_id} {self.order_type} - MPA: {self.mpa_account}"


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


class TerminateContext(OrderContext):
    @property
    def terminating_subscriptions_aws_account_ids(self):
        """
        Return a list of aws account ids which subscriptions are terminating
        :return: ["000000000000",]
        """
        return [
            s.get("externalIds", {}).get("vendor")
            for s in self.order.get("subscriptions", [])
            if s.get("status") == "Terminating"
        ]

    def __str__(self):
        return (
            super().__str__() + f" - Terminate - Terminating AWS Accounts: "
            f"{", ".join(self.terminating_subscriptions_aws_account_ids)}"
        )
