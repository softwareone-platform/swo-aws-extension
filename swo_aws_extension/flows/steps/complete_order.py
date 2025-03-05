import logging

from swo.mpt.client.mpt import complete_order, get_product_template_or_default
from swo.mpt.extensions.flows.pipeline import Step

from swo_aws_extension.flows.order import MPT_ORDER_STATUS_COMPLETED
from swo_aws_extension.notifications import send_email_notification

logger = logging.getLogger(__name__)

class CompleteOrder(Step):
    def __init__(self, template_name):
        self.template_name = template_name

    def __call__(self, client, context, next_step):
        template = get_product_template_or_default(
            client,
            context.product_id,
            MPT_ORDER_STATUS_COMPLETED,
            self.template_name,
        )
        agreement = context.order["agreement"]
        context.order = complete_order(
            client,
            context.order_id,
            template,
            parameters=context.order["parameters"],
        )
        context.order["agreement"] = agreement
        send_email_notification(client, context.order)
        logger.info(f"{context}: order has been completed successfully")
        next_step(client, context)

