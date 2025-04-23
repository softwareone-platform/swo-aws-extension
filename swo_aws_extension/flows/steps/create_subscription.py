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


class CreateSubscription(Step):
    def __call__(self, client: MPTClient, context: PurchaseContext, next_step):
        if get_phase(context.order) != PhasesEnum.CREATE_SUBSCRIPTIONS:
            logger.info(
                f"{context.order_id} - Skip - Current phase is '{get_phase(context.order)}', "
                f"skipping as it is not '{PhasesEnum.CREATE_SUBSCRIPTIONS}'"
            )
            next_step(client, context)
            return

        if context.is_purchase_order() and (
            context.is_type_transfer_with_organization()
            or context.is_type_transfer_without_organization()
        ):
            accounts = context.aws_client.list_accounts()
            account = find_first(
                lambda acc: acc["Status"] == "ACTIVE",
                accounts,
            )
            if not account:
                logger.exception(
                    f"{context.order_id} - Exception - "
                    f"Unable to find an active account: {accounts}"
                )
                return
            account_id = account["Id"]
            account_email = account["Email"]
            account_name = account["Name"]

        else:
            account_id = context.account_creation_status.account_id
            account_email = get_account_email(context.order)
            account_name = get_account_name(context.order)

        if not self.subscription_exist_for_account_id(client, context.order_id, account_id):
            logger.info(
                f"{context.order_id} - Intent - " f"Creating subscription for account {account_id}"
            )

            self.add_subscription(
                client,
                context,
                account_id,
                account_email,
                account_name,
            )

        context.order = set_phase(context.order, PhasesEnum.CCP_ONBOARD)
        update_order(client, context.order_id, parameters=context.order["parameters"])

        logger.info(
            f"'{context.order_id} - Action - {PhasesEnum.CREATE_SUBSCRIPTIONS}' "
            f"completed successfully. "
            f"Proceeding to next phase '{PhasesEnum.CCP_ONBOARD}'"
        )
        next_step(client, context)

    @staticmethod
    def subscription_exist_for_account_id(client, order_id, account_id):
        """
        Check if a subscription for the account already exists
        """
        order_subscription = get_order_subscription_by_external_id(
            client,
            order_id,
            account_id,
        )
        return order_subscription is not None

    @staticmethod
    def add_subscription(client, context, account_id, account_email, account_name):
        subscription = {
            "name": f"Subscription for {account_name} ({account_id})",
            "autoRenew": True,
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
        logger.info(
            f"{context.order_id} - Action -  subscription for {account_id} "
            f"({subscription["id"]}) created"
        )


class SynchronizeAgreementSubscriptionsStep(CreateSubscription):
    def __call__(self, client: MPTClient, context: PurchaseContext, next_step):
        logger.info(f"{context.order_id} - Start - Synchronize agreement subscriptions")
        agreement = get_agreement(client, context.order["agreement"]["id"])
        sync_agreement_subscriptions(client, context.aws_client, agreement)
        logger.info(f"{context.order_id} - Completed - Synchronize agreement subscriptions")
        next_step(client, context)
