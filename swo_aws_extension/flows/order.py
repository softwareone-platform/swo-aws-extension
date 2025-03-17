from dataclasses import dataclass
from datetime import date

from swo.mpt.extensions.flows.context import Context as BaseContext

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.parameters import Parameters, get_phase
from swo_aws_extension.utils import find_first

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
    due_date: date | None = None
    validation_succeeded: bool = True
    type: str | None = None
    product_id: str | None = None
    agreement_id: str | None = None
    order_id: str | None = None
    authorization_id: str | None = None
    seller_id: str | None = None
    phase: str | None = None
    aws_client: AWSClient | None = None

    def __str__(self):
        due_date = self.due_date.strftime("%Y-%m-%d") if self.due_date else "-"
        return (
            f"{self.product_id} {(self.type or '-').upper()} {self.agreement_id} {self.order_id} "
            f"{self.authorization_id} {due_date} "
        )


    @property
    def parameters(self) -> Parameters:
        return Parameters(self.order)

    @staticmethod
    def from_order(order: dict) -> "OrderContext":
        return OrderContext(
            order=order,
            product_id=order["product"]["id"],
            agreement_id=order["agreement"]["id"],
            order_id=order["id"],
            authorization_id=order["authorization"]["id"],
            seller_id=order["seller"]["id"],
            phase=get_phase(order),
        )


def get_subscription_by_line_and_item_id(subscriptions, item_id, line_id):
    """
    Return a subscription by line id and sku.

    Args:
        subscriptions (list): a list of subscription obects.
        vendor_external_id (str): the item SKU
        line_id (str): the id of the order line that should contain the given SKU.

    Returns:
        dict: the corresponding subscription if it is found, None otherwise.
    """
    for subscription in subscriptions:
        item = find_first(
            lambda x: x["id"] == line_id and x["item"]["id"] == item_id,
            subscription["lines"],
        )

        if item:
            return subscription
