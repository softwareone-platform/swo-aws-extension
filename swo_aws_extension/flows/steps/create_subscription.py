import logging

from mpt_extension_sdk.flows.pipeline import Step
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import (
    create_subscription,
    get_order_subscription_by_external_id,
    update_order,
)

from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.parameters import (
    FulfillmentParametersEnum,
    get_account_email,
    get_account_name,
    get_phase,
    set_phase,
)

logger = logging.getLogger(__name__)


class CreateSubscription(Step):
    def __call__(self, client: MPTClient, context: PurchaseContext, next_step):
        if get_phase(context.order) != PhasesEnum.CREATE_SUBSCRIPTIONS:
            logger.info(
                f"Current phase is '{get_phase(context.order)}', "
                f"skipping as it is not '{PhasesEnum.CREATE_SUBSCRIPTIONS}'"
            )
            next_step(client, context)
            return
        if context.is_purchase_order() and context.is_type_transfer_with_organization():
            self.create_subscriptions_from_organization(client, context)
        elif context.is_purchase_order() or context.is_change_order():
            self.create_subscription_from_new_account(client, context)
        context.order = set_phase(context.order, PhasesEnum.CCP_ONBOARD)
        update_order(client, context.order_id, parameters=context.order["parameters"])
        logger.info(
            f"'{PhasesEnum.CREATE_SUBSCRIPTIONS}' completed successfully. "
            f"Proceeding to next phase '{PhasesEnum.CCP_ONBOARD}'"
        )
        next_step(client, context)

    def create_subscription_from_new_account(self, client, context):
        account_id = context.account_creation_status.account_id
        if not self.subscription_exist_for_account_id(client, context.order_id, account_id):
            logger.info(f"Creating subscription for account {account_id}")
            account_email = get_account_email(context.order)
            account_name = get_account_name(context.order)

            self.add_subscription(
                client,
                context,
                account_id,
                account_email,
                account_name,
            )

    def subscription_exist_for_account_id(self, client, order_id, account_id):
        """
        Check if a subscription for the account already exists
        """
        order_subscription = get_order_subscription_by_external_id(
            client,
            order_id,
            account_id,
        )
        return order_subscription is not None

    def create_subscriptions_from_organization(self, client, context):
        # list aws organization accounts
        # check if a subscriptioon for the account already exists. if exist, continue
        # create a subscription for each organization account
        accounts = context.aws_client.list_accounts()

        for account in accounts:
            account_id = account["Id"]
            account_email = account["Email"]
            account_name = account["Name"]
            account_state = account["Status"]
            if account_state != "ACTIVE":
                logger.info(
                    f"{context.order_id} - Skipping - "
                    f"Import Account {account_id} as it is not active"
                )
                continue
            if self.subscription_exist_for_account_id(client, context.order_id, account_id):
                logger.info(
                    f"{context.order_id} - Skipping - Create subscription for "
                    f"account={account_id} email={account_email} as it already exist"
                )
                continue

            self.add_subscription(
                client,
                context,
                account_id,
                account_email,
                account_name,
            )

    def add_subscription(self, client, context, account_id, account_email, account_name):
        subscription = {
            "name": f"Subscription for {account_id}",
            "parameters": {
                "fulfillment": [
                    {
                        "externalId": FulfillmentParametersEnum.ACCOUNT_EMAIL,
                        "value": account_email,
                    },
                    {
                        "externalId": FulfillmentParametersEnum.ACCOUNT_NAME,
                        "value": account_name,
                    },
                ]
            },
            "externalIds": {
                "vendor": account_id,
            },
            "lines": [
                {
                    "id": context.order["lines"][0]["id"],
                },
            ],
        }
        subscription = create_subscription(client, context.order_id, subscription)
        logger.info(f"{context}: subscription for {account_id} " f'({subscription["id"]}) created')


class CreateOrganizationSubscriptions(CreateSubscription):
    def __call__(self, client: MPTClient, context: PurchaseContext, next_step):
        logger.info(f"{context.order_id} - Start - Create organization subscriptions")
        self.create_subscriptions_from_organization(client, context)
        logger.info(f"{context.order_id} - Completed - Create organization subscriptions")
        next_step(client, context)
