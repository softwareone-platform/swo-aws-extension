import logging

from mpt_extension_sdk.flows.pipeline import Step

from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.template import TemplateNameManager
from swo_aws_extension.parameters import get_phase, set_account_request_id

logger = logging.getLogger(__name__)


class CompleteOrderStep(Step):
    def __call__(self, client, context, next_step):
        self._complete_order(client, context)
        next_step(client, context)

    def _complete_order(self, client, context: InitialAWSContext):
        template_name = TemplateNameManager.complete(context)
        context.switch_order_status_to_complete(client, template_name)
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
