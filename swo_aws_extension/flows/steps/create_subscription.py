import logging

from mpt_extension_sdk.flows.pipeline import Step
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import (
    create_subscription,
    get_agreement,
    get_order_subscription_by_external_id,
    update_order,
)
from mpt_extension_sdk.mpt_http.utils import find_first

from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.jobs.synchronize_agreements import sync_agreement_subscriptions
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.parameters import (
    FulfillmentParametersEnum,
    get_account_email,
    get_account_name,
    get_phase,
    set_phase,
)

logger = logging.getLogger(__name__)


def subscription_exist_for_account_id(client: MPTClient, order_id: str, account_id: str) -> bool:
    """Check if a subscription for the account already exists."""
    order_subscription = get_order_subscription_by_external_id(
        client,
        order_id,
        account_id,
    )
    return order_subscription is not None


def add_subscription(
    client: MPTClient,
    context: PurchaseContext,
    account_id: str,
    account_email: str,
    account_name: str,
):
    """
    Add a subscription for the new AWS account created.

    Args:
        client: The MPT client instance.
        context: The purchase context.
        account_id: The ID of the AWS account.
        account_email: The email associated with the AWS account.
        account_name: The name of the AWS account.
    """
    logger.info("%s - Intent - Creating subscription for account %s", context.order_id, account_id)

    subscription = {
        "name": f"Subscription for {account_name} ({account_id})",
        "autoRenew": True,
        "parameters": {
            "fulfillment": [
                {
                    "externalId": FulfillmentParametersEnum.ACCOUNT_EMAIL.value,
                    "value": account_email,
                },
                {
                    "externalId": FulfillmentParametersEnum.ACCOUNT_NAME.value,
                    "value": account_name,
                },
            ]
        },
        "externalIds": {
            "vendor": account_id,
        },
        "lines": [{"id": order_line["id"]} for order_line in context.order["lines"]],
    }
    subscription = create_subscription(client, context.order_id, subscription)
    context.subscriptions.append(subscription)
    logger.info(
        "%s - Action -  subscription for %s (%s) created",
        context.order_id,
        account_id,
        subscription["id"],
    )


class CreateSubscription(Step):
    """Create subscription on MPT."""

    def __call__(self, client: MPTClient, context: PurchaseContext, next_step):
        """Execute step."""
        if get_phase(context.order) != PhasesEnum.CREATE_SUBSCRIPTIONS:
            logger.info(
                "%s - Skip - Current phase is '%s', skipping as it is not '%s'",
                context.order_id,
                get_phase(context.order),
                PhasesEnum.CREATE_SUBSCRIPTIONS.value,
            )
            next_step(client, context)
            return

        if context.is_purchase_order() and (
            context.is_type_transfer_with_organization()
            or context.is_type_transfer_without_organization()
        ):
            accounts = context.aws_client.list_accounts()
            account = find_first(
                lambda acc: acc["Status"] == "ACTIVE" and acc["Id"] != context.mpa_account,
                accounts,
            )
            if not account:
                logger.error(
                    "%s - Exception - Unable to find an active account: %s",
                    context.order_id,
                    accounts,
                )
                return
            account_id = account["Id"]
            account_email = account["Email"]
            account_name = account["Name"]

        else:
            account_id = context.account_creation_status.account_id
            account_email = get_account_email(context.order)
            account_name = get_account_name(context.order)

        if not subscription_exist_for_account_id(client, context.order_id, account_id):
            add_subscription(
                client,
                context,
                account_id,
                account_email,
                account_name,
            )
        next_phase = (
            PhasesEnum.COMPLETED.value
            if context.is_split_billing()
            else PhasesEnum.CCP_ONBOARD.value
        )
        context.order = set_phase(context.order, next_phase)
        update_order(client, context.order_id, parameters=context.order["parameters"])

        logger.info(
            "'%s - Action - %s' completed successfully. Proceeding to next phase '%s'",
            context.order_id,
            PhasesEnum.CREATE_SUBSCRIPTIONS.value,
            next_phase,
        )
        next_step(client, context)


class SynchronizeAgreementSubscriptionsStep(CreateSubscription):
    """Run agreement synchronization."""

    def __call__(self, client: MPTClient, context: PurchaseContext, next_step):
        """Execute step."""
        logger.info("%s - Start - Synchronize agreement subscriptions", context.order_id)
        agreement = get_agreement(client, context.agreement["id"])
        sync_agreement_subscriptions(client, context.aws_client, agreement)
        logger.info("%s - Completed - Synchronize agreement subscriptions", context.order_id)
        next_step(client, context)


class CreateChangeSubscriptionStep(Step):
    """Add subscription."""

    def __call__(self, client: MPTClient, context: PurchaseContext, next_step):
        """Execute step."""
        account_id = context.account_creation_status.account_id

        if not subscription_exist_for_account_id(client, context.order_id, account_id):
            add_subscription(
                client,
                context,
                account_id,
                context.root_account_email,
                context.account_name,
            )

        logger.info(
            "%s - Action - Create Change Subscription completed successfully. ",
            context.order_id,
        )
        next_step(client, context)
