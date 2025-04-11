import copy
from dataclasses import dataclass

from mpt_extension_sdk.flows.context import Context as BaseContext
from mpt_extension_sdk.mpt_http.mpt import get_product_template_or_default, query_order
from pyairtable.orm import Model

from swo_aws_extension.aws.client import AccountCreationStatus, AWSClient
from swo_aws_extension.constants import SupportTypesEnum, TransferTypesEnum
from swo_aws_extension.notifications import send_email_notification
from swo_aws_extension.parameters import (
    get_account_id,
    get_ccp_engagement_id,
    get_master_payer_id,
    get_mpa_account_id,
    get_support_type,
    get_termination_type_parameter,
    get_transfer_type,
)

MPT_ORDER_STATUS_PROCESSING = "Processing"
MPT_ORDER_STATUS_QUERYING = "Querying"
MPT_ORDER_STATUS_COMPLETED = "Completed"


def is_partner_led_support_enabled(order):
    return get_support_type(order) == SupportTypesEnum.PARTNER_LED_SUPPORT


@dataclass
class InitialAWSContext(BaseContext):
    validation_succeeded: bool = True
    aws_client: AWSClient | None = None
    airtable_mpa: Model | None = None
    account_creation_status: AccountCreationStatus | None = None

    @property
    def mpa_account(self):
        try:
            return get_mpa_account_id(self.order)
        except (AttributeError, KeyError, TypeError):
            return None

    @property
    def pls_enabled(self):
        return is_partner_led_support_enabled(self.order)

    def is_type_transfer_with_organization(self):
        return get_transfer_type(self.order) == TransferTypesEnum.TRANSFER_WITH_ORGANIZATION

    def is_type_transfer_without_organization(self):
        return get_transfer_type(self.order) == TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION


@dataclass
class PurchaseContext(InitialAWSContext):
    @property
    def order_master_payer_id(self):
        """
        Return the master payer id of the order
        """
        try:
            return get_master_payer_id(self.order)
        except (AttributeError, KeyError, TypeError):
            return None

    def get_account_ids(self) -> set[str]:
        """
        Return the account ids of the order parameter (orderAccountId)
        cleaned and as a set of strings
        """
        accounts_txt = get_account_id(self.order)
        if not accounts_txt:
            return set()
        accounts = {line.strip() for line in accounts_txt.split("\n") if line.strip()}
        return set(accounts)

    @property
    def ccp_engagement_id(self):
        return get_ccp_engagement_id(self.order)

    def __str__(self):
        return f"PurchaseContext: {self.order_id} {self.order_type} - MPA: {self.mpa_account}"


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


class TerminateContext(InitialAWSContext):
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

    @property
    def termination_type(self):
        """
        Return the termination type
        :return: "CloseAccount" or "UnlinkAccount"
        """
        return get_termination_type_parameter(self.order)

    def __str__(self):
        return (
            super().__str__() + f" - Terminate - Terminating AWS Accounts: "
            f"{", ".join(self.terminating_subscriptions_aws_account_ids)}"
        )
