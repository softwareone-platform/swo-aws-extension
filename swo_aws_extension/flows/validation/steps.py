import logging

from mpt_extension_sdk.flows.pipeline import Step
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import get_product_items_by_skus

from swo_aws_extension.constants import AWS_ITEMS_SKUS
from swo_aws_extension.flows.order import PurchaseContext

logger = logging.getLogger(__name__)


class InitializeItemStep(Step):
    def __call__(self, client: MPTClient, context: PurchaseContext, next_step):
        items = get_product_items_by_skus(
            client, context.order.get("product", {}).get("id", ""), AWS_ITEMS_SKUS
        )
        if not items:
            logger.error(
                f"{context.order_id} - Failed to get product items with skus {AWS_ITEMS_SKUS}"
            )
            return
        items = [{"item": item, "quantity": 1} for item in items]
        context.order["lines"] = items
        next_step(client, context)
