import logging

from mpt_extension_sdk.flows.pipeline import Step
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import (
    create_subscription,
    get_order_subscription_by_external_id,
    update_order,
)

from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.parameters import (
    FulfillmentParametersEnum,
    get_account_email,
    get_account_name,
    get_phase,
    set_phase,
)

logger = logging.getLogger(__name__)


class CreateSubscription(Step):
    def __call__(self, client: MPTClient, context, next_step):
        if get_phase(context.order) != PhasesEnum.CREATE_SUBSCRIPTIONS:
            logger.info(
                f"Current phase is '{get_phase(context.order)}', "
                f"skipping as it is not '{PhasesEnum.CREATE_SUBSCRIPTIONS}'"
            )
            next_step(client, context)
            return
        if context.is_purchase_order() or context.is_change_order():
            account_id = context.account_creation_status.account_id
            order_subscription = get_order_subscription_by_external_id(
                client,
                context.order["id"],
                account_id,
            )
            if not order_subscription:
                logger.info(f"Creating subscription for account {account_id}")
                account_email = get_account_email(context.order)
                account_name = get_account_name(context.order)

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
                logger.info(
                    f"{context}: subscription for {account_id} " f'({subscription["id"]}) created'
                )
        context.order = set_phase(context.order, PhasesEnum.COMPLETED)
        update_order(client, context.order_id, parameters=context.order["parameters"])
        logger.info(
            f"'{PhasesEnum.CREATE_SUBSCRIPTIONS}' completed successfully. "
            f"Proceeding to next phase '{PhasesEnum.COMPLETED}'"
        )
        next_step(client, context)
