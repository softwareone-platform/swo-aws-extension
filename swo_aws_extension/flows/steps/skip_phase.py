import logging
from typing import override

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.errors import SkipStepError
from swo_aws_extension.parameters import get_phase, set_phase

logger = logging.getLogger(__name__)


class SkipPhaseStep(BasePhaseStep):
    """Skip Phase step.

    Moves an order from a phase that no other step of the pipeline handles to the
    next phase of the pipeline, so that the order does not stay in that phase.
    """

    def __init__(self, phase: PhasesEnum, next_phase: PhasesEnum):
        self._phase = phase
        self._next_phase = next_phase

    @override
    def pre_step(self, context: PurchaseContext) -> None:
        phase = get_phase(context.order)
        if phase != self._phase:
            raise SkipStepError(
                f"{context.order_id} - Next - Current phase is '{phase}', skipping as it"
                f" is not '{self._phase}'"
            )

    @override
    def process(self, client: MPTClient, context: PurchaseContext) -> None:
        logger.info(
            "%s - Action - Moving phase '%s' to '%s'",
            context.order_id,
            self._phase,
            self._next_phase,
        )
        context.order = set_phase(context.order, self._next_phase)

    @override
    def post_step(self, client: MPTClient, context: PurchaseContext) -> None:
        context.order = update_order(
            client, context.order_id, parameters=context.order["parameters"]
        )
