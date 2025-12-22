import logging
from dataclasses import dataclass

from mpt_extension_sdk.flows.context import Context as BaseContext

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.constants import AccountTypesEnum
from swo_aws_extension.parameters import (
    get_account_type,
    get_phase,
)

logger = logging.getLogger(__name__)


@dataclass
class InitialAWSContext(BaseContext):
    """AWS order processing context."""

    aws_client: AWSClient | None = None
    agreement: dict | None = None
    seller: dict | None = None
    buyer: dict | None = None
    subscriptions: list[dict] | None = None

    @property
    def pm_account_id(self):
        """Program Management Account if exists."""
        return self.order.get("authorization", {}).get("externalIds", {}).get("operations")

    @property
    def master_payer_account_id(self):
        """Get Master Payer Account ID from agreement."""
        return self.agreement.get("externalIds", {}).get("vendor", "")

    @property
    def order_status(self):
        """Return the order status."""
        return self.order.get("status")

    @property
    def template(self):
        """Return the order template."""
        return self.order.get("template")

    def is_type_new_aws_environment(self):
        """Is create a new AWS environment."""
        return get_account_type(self.order) == AccountTypesEnum.NEW_AWS_ENVIRONMENT

    def is_type_existing_aws_environment(self):
        """Is transfer without organization."""
        return get_account_type(self.order) == AccountTypesEnum.EXISTING_AWS_ENVIRONMENT

    @classmethod
    def from_order_data(cls, order: dict):
        """
        Initialize an InitialAWSContext instance from an order dictionary.

        Args:
            order: The order data.

        Returns:
            InitialAWSContext: An instance of InitialAWSContext with populated fields.
        """
        return cls(
            agreement=order.pop("agreement", {}),
            seller=order.pop("seller", {}),
            buyer=order.pop("buyer", {}),
            subscriptions=order.get("subscriptions", []),
            order=order,
        )


@dataclass
class PurchaseContext(InitialAWSContext):
    """Order purchase context."""

    @property
    def phase(self):
        """Order phase."""
        return get_phase(self.order)

    @property
    def authorization_id(self):
        """Authorization ID from the order."""
        return self.order.get("authorization", {}).get("id")

    @property
    def currency(self):
        """Currency from the order."""
        return self.order.get("price", {}).get("currency")

    def __str__(self):
        return f"PurchaseContext: {self.order_id} {self.order_type}"
