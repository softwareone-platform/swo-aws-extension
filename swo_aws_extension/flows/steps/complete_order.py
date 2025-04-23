import logging

from mpt_extension_sdk.flows.pipeline import Step
from mpt_extension_sdk.mpt_http.mpt import complete_order, get_product_template_or_default

from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.order import MPT_ORDER_STATUS_COMPLETED
from swo_aws_extension.notifications import send_email_notification
from swo_aws_extension.parameters import get_phase

logger = logging.getLogger(__name__)


class CompleteOrder(Step):
    def __init__(self, template_name):
        self.template_name = template_name

    def __call__(self, client, context, next_step):
        self._complete_order(client, context)
        next_step(client, context)

    def _complete_order(self, client, context):
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
        logger.info(f"{context.order_id} - Completed - order has been completed successfully")


class CompletePurchaseOrder(CompleteOrder):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __call__(self, client, context, next_step):
        if get_phase(context.order) != PhasesEnum.COMPLETED:
            logger.info(
                f"{context.order_id} - Skip - Current phase is '{get_phase(context.order)}', "
                f"skipping as it is not '{PhasesEnum.COMPLETED}'"
            )
            next_step(client, context)
            return
        self._complete_order(client, context)
        next_step(client, context)
