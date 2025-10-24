import logging

from mpt_extension_sdk.flows.pipeline import Step

from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.template import TemplateNameManager
from swo_aws_extension.parameters import get_phase, set_account_request_id

logger = logging.getLogger(__name__)


class CompleteOrderStep(Step):
    """Complete order with template."""

    def __call__(self, client, context, next_step):
        """Execute step."""
        self._complete_order(client, context)
        next_step(client, context)

    def _complete_order(self, client, context: InitialAWSContext):
        template_name = TemplateNameManager.complete(context)
        context.switch_order_status_to_complete(client, template_name)
        logger.info("%s - Completed - order has been completed successfully", context.order_id)


class CompletePurchaseOrderStep(CompleteOrderStep):
    """Complete purchase order."""

    def __call__(self, client, context, next_step):
        """Execute step."""
        if get_phase(context.order) != PhasesEnum.COMPLETED:
            logger.info(
                "%s - Skip - Current phase is '{get_phase(context.order)}', "
                "skipping as it is not '%s'",
                context.order_id,
                PhasesEnum.COMPLETED.value,
            )
            next_step(client, context)
            return
        context.order = set_account_request_id(context.order, "")
        self._complete_order(client, context)
        next_step(client, context)


class CompleteChangeOrderStep(CompleteOrderStep):
    """Complete change order."""

    def __call__(self, client, context, next_step):
        """Exececute step."""
        context.order = set_account_request_id(context.order, "")
        self._complete_order(client, context)
        next_step(client, context)


class CompleteTerminationOrderStep(CompleteOrderStep):
    """Complete termination order."""

    def __call__(self, client, context, next_step):
        """Execute step."""
        context.order = set_account_request_id(context.order, "")
        self._complete_order(client, context)
        next_step(client, context)
