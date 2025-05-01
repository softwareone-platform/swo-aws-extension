import logging

from mpt_extension_sdk.flows.pipeline import Step
from mpt_extension_sdk.mpt_http.mpt import complete_order

from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.order import MPT_ORDER_STATUS_COMPLETED, InitialAWSContext
from swo_aws_extension.flows.template import TemplateNameManager
from swo_aws_extension.notifications import send_email_notification
from swo_aws_extension.parameters import get_phase, set_account_request_id

logger = logging.getLogger(__name__)


class CompleteOrderStep(Step):
    def __call__(self, client, context, next_step):
        self._complete_order(client, context)
        next_step(client, context)

    def get_template_name(self, context: InitialAWSContext):
        return TemplateNameManager.complete(context)

    def _complete_order(self, client, context: InitialAWSContext):
        template_name = self.get_template_name(context)
        context.update_template(client, MPT_ORDER_STATUS_COMPLETED, template_name)
        context.order = complete_order(
            client,
            context.order_id,
            template=context.template,
            parameters=context.order["parameters"],
        )
        send_email_notification(client, context.order, context.buyer)
        logger.info(f"{context.order_id} - Completed - order has been completed successfully")


class CompletePurchaseOrderStep(CompleteOrderStep):
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
        context.order = set_account_request_id(context.order, "")
        self._complete_order(client, context)
        next_step(client, context)


class CompleteChangeOrderStep(CompleteOrderStep):
    def __call__(self, client, context, next_step):
        context.order = set_account_request_id(context.order, "")
        self._complete_order(client, context)
        next_step(client, context)


class CompleteTerminationOrderStep(CompleteOrderStep):
    def __call__(self, client, context, next_step):
        context.order = set_account_request_id(context.order, "")
        self._complete_order(client, context)
        next_step(client, context)
