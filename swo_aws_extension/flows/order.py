import copy
import logging
from dataclasses import dataclass

from mpt_extension_sdk.flows.context import Context as BaseContext
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import fail_order, get_product_template_or_default, query_order

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.constants import AccountTypesEnum
from swo_aws_extension.notifications import MPTNotificationManager
from swo_aws_extension.parameters import (
    get_account_type,
    get_phase,
)

logger = logging.getLogger(__name__)
MPT_ORDER_STATUS_QUERYING = "Querying"


def set_template(order, template):
    """Set the template in the order."""
    updated_order = copy.deepcopy(order)
    updated_order["template"] = template
    return updated_order


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


def set_order_template(
    client: MPTClient, context: InitialAWSContext, status: str, template_name: str
):
    """Get the rendered template from MPT API."""
    template = get_product_template_or_default(
        client,
        context.order["product"]["id"],
        status,
        template_name,
    )
    found_template_name = template.get("name")
    if found_template_name != template_name:
        logger.info(
            "%s - Template error - Template template_name=`%s` not found for status `%s`. "
            "Using template_name=`%s` instead. Please check the template name and template setup"
            " in the MPT platform.",
            context.order_id,
            template_name,
            status,
            found_template_name,
        )
    context.order = set_template(context.order, template)
    logger.info("%s - Action - Updated template to %s", context.order_id, template_name)
    return context.order["template"]


def switch_order_status_to_query_and_notify(
    client: MPTClient, context: InitialAWSContext, template_name: str
):
    """Switch the order status to 'Querying' if it is not already in that status."""
    set_order_template(client, context, MPT_ORDER_STATUS_QUERYING, template_name)
    kwargs = {
        "parameters": context.order["parameters"],
        "template": context.template,
    }
    if context.order.get("error"):
        kwargs["error"] = context.order["error"]

    context.order = query_order(
        client,
        context.order_id,
        **kwargs,
    )
    MPTNotificationManager(client).send_notification(context)


def switch_order_status_to_failed_and_notify(
    client: MPTClient, context: InitialAWSContext, error: str
):
    """Switch the order status to 'Failed'."""
    kwargs = {
        "parameters": context.order["parameters"],
    }

    context.order = fail_order(
        client,
        context.order_id,
        error,
        **kwargs,
    )
    MPTNotificationManager(client).send_notification(context)
