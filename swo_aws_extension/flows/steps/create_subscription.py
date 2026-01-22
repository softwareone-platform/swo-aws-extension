import logging
from typing import override

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import (
    create_subscription,
    get_order_subscription_by_external_id,
    update_order,
)

from swo_aws_extension.config import Config
from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.errors import SkipStepError
from swo_aws_extension.parameters import get_mpa_account_id, get_phase, set_phase

logger = logging.getLogger(__name__)


class CreateSubscription(BasePhaseStep):
    """Handles the creation of a subscription."""

    def __init__(self, config: Config):
        self._config = config

    @override
    def pre_step(self, context: PurchaseContext) -> None:
        phase = get_phase(context.order)
        if phase != PhasesEnum.CREATE_SUBSCRIPTION:
            raise SkipStepError(
                f"{context.order_id} - Next - Current phase is '{phase}', skipping as it"
                f" is not '{PhasesEnum.CREATE_SUBSCRIPTION}'"
            )

    @override
    def process(self, client: MPTClient, context: PurchaseContext) -> None:
        mpa_id = get_mpa_account_id(context.order)
        order_subscription = get_order_subscription_by_external_id(client, context.order_id, mpa_id)
        if order_subscription is not None:
            logger.info(
                "%s - Skip - Subscription for account %s already exists, skipping creation",
                context.order_id,
                mpa_id,
            )
            return

        logger.info("%s - Intent - Creating subscription for account %s", context.order_id, mpa_id)

        subscription = {
            "name": f"Subscription for {mpa_id}",
            "autoRenew": True,
            "externalIds": {
                "vendor": mpa_id,
            },
            "lines": [{"id": order_line["id"]} for order_line in context.order["lines"]],
        }
        subscription = create_subscription(client, context.order_id, subscription)
        context.subscriptions.append(subscription)
        logger.info(
            "%s - Action - subscription for %s (%s) created",
            context.order_id,
            mpa_id,
            subscription["id"],
        )

    @override
    def post_step(self, client: MPTClient, context: PurchaseContext) -> None:
        context.order = set_phase(context.order, PhasesEnum.COMPLETED)
        context.order = update_order(
            client, context.order_id, parameters=context.order["parameters"]
        )
