import copy
import logging
from dataclasses import dataclass

from mpt_extension_sdk.flows.context import Context as BaseContext
from mpt_extension_sdk.mpt_http.mpt import (
    complete_order,
    get_product_template_or_default,
    query_order,
    update_order,
)
from mpt_extension_sdk.mpt_http.wrap_http_error import wrap_mpt_http_error
from pyairtable.orm import Model

from swo_aws_extension.aws.client import AccountCreationStatus, AWSClient
from swo_aws_extension.constants import SupportTypesEnum, TransferTypesEnum
from swo_aws_extension.parameters import (
    ChangeOrderParametersEnum,
    OrderParametersEnum,
    get_account_id,
    get_ccp_engagement_id,
    get_master_payer_id,
    get_parameter_value,
    get_phase,
    get_support_type,
    get_termination_type_parameter,
    get_transfer_type,
)
from swo_aws_extension.shared import mpt_notifier

MPT_ORDER_STATUS_PROCESSING = "Processing"
MPT_ORDER_STATUS_QUERYING = "Querying"
MPT_ORDER_STATUS_COMPLETED = "Completed"


logger = logging.getLogger(__name__)


def is_partner_led_support_enabled(order: dict) -> bool:
    """Is AWS partner support enabled."""
    return get_support_type(order) == SupportTypesEnum.PARTNER_LED_SUPPORT


def set_template(order: dict, template: dict) -> dict:
    """Setup template."""
    updated_order = copy.deepcopy(order)
    updated_order["template"] = template
    return updated_order


class OrderStatusChangeError(RuntimeError):
    """Exception raised when the order status cannot be changed."""
    def __init__(self, target_status, current_status):
        message = (
            f"Order is already in `{current_status}` status. "
            f"Unable to switch and order to `{target_status}` "
            f"when it is in `{current_status}` status."
        )
        super().__init__(message)


# TODO: SDK candidate
@wrap_mpt_http_error
def process_order(client, order_id, **kwargs):
    """
    Update the order status to PROCESS.

    Args:
        client (MPTClient): The MPT client instance.
        order_id (str): The ID of the order to process.
        **kwargs: Additional parameters to pass to the order processing.
    """
    response = client.post(
        f"/commerce/orders/{order_id}/process",
        json=kwargs,
    )
    response.raise_for_status()
    return response.json()


def reset_order_error(order: dict) -> dict:
    """
    Reset the error field of an order.

    Args:
        order: The order to reset the error field of

    Returns:
        The updated order
    """
    updated_order = copy.deepcopy(order)
    updated_order["error"] = None
    return updated_order


@dataclass
class InitialAWSContext(BaseContext):
    """AWS order processing context."""
    validation_succeeded: bool = True
    aws_client: AWSClient | None = None
    airtable_mpa: Model | None = None
    account_creation_status: AccountCreationStatus | None = None
    agreement: dict | None = None
    seller: dict | None = None
    buyer: dict | None = None
    subscriptions: list[dict] | None = None

    @property
    def mpa_account(self):
        """Master payer account if exists."""
        try:
            return self.agreement.get("externalIds", {}).get("vendor", "")
        except (AttributeError, KeyError, TypeError):
            return None

    @property
    def pls_enabled(self):
        """If PLS is enabled."""
        return is_partner_led_support_enabled(self.order)

    @property
    def seller_country(self):
        """Seller country."""
        country = self.seller.get("address", {}).get("country", "")
        if not country:
            raise ValueError(f"{self.order_id} - Seller country is not included in the order.")
        return country

    def is_type_transfer_with_organization(self):
        """Is transfer with organization."""
        return get_transfer_type(self.order) == TransferTypesEnum.TRANSFER_WITH_ORGANIZATION

    def is_type_transfer_without_organization(self):
        """Is transfer without organization."""
        return get_transfer_type(self.order) == TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION

    def is_split_billing(self):
        """If is split billing."""
        return get_transfer_type(self.order) == TransferTypesEnum.SPLIT_BILLING

    @property
    def order_status(self):
        """Return the order state."""
        return self.order.get("status")

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

    @property
    def template_name(self):
        """Order template name."""
        return self.order.get("template", {}).get("name")

    @property
    def template(self):
        """Order template."""
        return self.order.get("template")

    def _update_template(self, client, status, template_name):
        """Update the template name of the order."""
        template = get_product_template_or_default(
            client,
            self.order["product"]["id"],
            status,
            template_name,
        )
        found_template_name = template.get("name")
        if found_template_name != template_name:
            logger.error(
                "%s - Template error - Template template_name=`%s` not found for status `%s`. "
                "Using template_name=`%s` instead. "
                "Please check the template name and template setup in the MPT platform.",
                self.order_id, template_name, status, found_template_name,
            )
        self.order = set_template(self.order, template)
        logger.info("%s - Action - Updated template to %s", self.order_id, template_name)
        return self.order["template"]

    def update_processing_template(self, client, template_name):
        """
        Update the order parameters and template from a template name.

        Requires the order to be in processing status and the parameter to be a processing template

        Args:
            client (MPTClient): An instance of the Marketplace platform client.
            template_name (str): The name of the template to use.
        """
        if self.order_status != MPT_ORDER_STATUS_PROCESSING:
            raise RuntimeError(
                "Order is not in processing status. "
                f"Unable to set a processing template with an order in status={self.order_status}."
            )

        self._update_template(client, MPT_ORDER_STATUS_PROCESSING, template_name)
        self.order = update_order(
            client, self.order_id, parameters=self.order["parameters"], template=self.template
        )
        mpt_notifier.notify_re_order(self)

    def switch_order_status_to_process(self, client, template_name=None):
        """
        Switch the order status to PROCESS, change the template and update the order.

        Args:
            client (MPTClient): An instance of the Marketplace platform client.
            template_name (str): The name of the template to use.
        """
        if self.order_status == MPT_ORDER_STATUS_PROCESSING:
            raise OrderStatusChangeError(
                current_status=self.order_status, target_status=MPT_ORDER_STATUS_PROCESSING
            )

        kwargs = {}
        self._update_template(client, MPT_ORDER_STATUS_PROCESSING, template_name)
        kwargs["template"] = self.template
        kwargs["parameters"] = self.order["parameters"]

        self.order = process_order(client, self.order_id, **kwargs)
        mpt_notifier.notify_re_order(self)
        logger.info("%s - Action - Set order to processing", self.order_id)
        return self.order

    def switch_order_status_to_query(self, client, template_name=None):
        """
        Switches the status of an MPT order to 'query' and resetting due date.

        Initiating a query order process.

        Args:
            client (MPTClient): An instance of the Marketplace platform client.
            order (dict): The MPT order to be switched to 'query' status.
            buyer (dict): The buyer of the order.
            template_name: The name of the template to use, if None -> use default

        Returns:
            dict: The updated order.
        """
        if self.order_status == MPT_ORDER_STATUS_QUERYING:
            raise OrderStatusChangeError(
                current_status=self.order_status, target_status=MPT_ORDER_STATUS_QUERYING
            )

        self._update_template(client, MPT_ORDER_STATUS_QUERYING, template_name)
        kwargs = {
            "parameters": self.order["parameters"],
            "template": self.template,
        }
        if self.order.get("error"):
            kwargs["error"] = self.order["error"]

        self.order = query_order(
            client,
            self.order_id,
            **kwargs,
        )
        mpt_notifier.notify_re_order(self)

    def switch_order_status_to_complete(self, client, template_name=None):
        """Switch order to completed with template."""
        if self.order_status == MPT_ORDER_STATUS_COMPLETED:
            raise OrderStatusChangeError(
                current_status=self.order_status, target_status=MPT_ORDER_STATUS_COMPLETED
            )
        kwargs = {}
        self._update_template(client, MPT_ORDER_STATUS_COMPLETED, template_name)
        kwargs["template"] = self.template
        kwargs["parameters"] = self.order["parameters"]

        self.order = complete_order(client, self.order_id, **kwargs)
        mpt_notifier.notify_re_order(self)
        logger.info("%s - Action - Set order to completed", self.order_id)
        return self.order


@dataclass
class PurchaseContext(InitialAWSContext):
    """Order purchase context."""
    @property
    def order_master_payer_id(self):
        """Return the master payer id of the order."""
        try:
            return get_master_payer_id(self.order)
        except (AttributeError, KeyError, TypeError):
            return None

    def get_account_ids(self) -> set[str]:
        """Return the account ids of the order parameter cleaned and as a set of strings."""
        accounts_txt = get_account_id(self.order)
        if not accounts_txt:
            return set()
        accounts = {line.strip() for line in accounts_txt.split("\n") if line.strip()}
        return set(accounts)

    @property
    def ccp_engagement_id(self):
        """CCP engagement id."""
        return get_ccp_engagement_id(self.order)

    @property
    def phase(self):
        """Order phase."""
        return get_phase(self.order)

    @property
    def agreement_id(self):
        """Return the agreement id of the order."""
        try:
            return self.agreement.get("id")
        except (AttributeError, KeyError, TypeError):
            return None

    @property
    def root_account_email(self):
        """Return the root account email of the order."""
        return get_parameter_value(self.order, OrderParametersEnum.ROOT_ACCOUNT_EMAIL)

    @property
    def account_name(self):
        """Return the account name of the order."""
        return get_parameter_value(self.order, OrderParametersEnum.ACCOUNT_NAME)

    def __str__(self):
        return f"PurchaseContext: {self.order_id} {self.order_type} - MPA: {self.mpa_account}"


class TerminateContext(InitialAWSContext):
    """Terminate order processing context."""
    @property
    def terminating_subscriptions_aws_account_ids(self):
        """Return a list of aws account ids which subscriptions are terminating."""
        return [
            s.get("externalIds", {}).get("vendor")
            for s in self.subscriptions
            if s.get("status") == "Terminating"
        ]

    @property
    def termination_type(self):
        """Return the termination type."""
        return get_termination_type_parameter(self.order)

    def __str__(self):
        return (
            super().__str__() + f" - Terminate - Terminating AWS Accounts: "
            f"{', '.join(self.terminating_subscriptions_aws_account_ids)}"
        )


class ChangeContext(InitialAWSContext):
    """AWS Order change processing context."""
    @property
    def root_account_email(self):
        """Return the root account email of the order."""
        return get_parameter_value(self.order, ChangeOrderParametersEnum.ROOT_ACCOUNT_EMAIL)

    @property
    def account_name(self):
        """Return the account name of the order."""
        return get_parameter_value(self.order, ChangeOrderParametersEnum.ACCOUNT_NAME)

    def __str__(self):
        return (
            super().__str__()
            + f" - Change - Creating AWS Account: {self.account_name} - {self.root_account_email}"
        )
