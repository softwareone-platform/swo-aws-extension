from typing import override

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.errors import SkipStepError
from swo_aws_extension.parameters import get_phase, set_phase


class OnboardServices(BasePhaseStep):
    """Onboard Services step."""

    @override
    def pre_step(self, context: PurchaseContext) -> None:
        """Hook to run before the step processing."""
        phase = get_phase(context.order)
        if phase != PhasesEnum.ONBOARD_SERVICES:
            raise SkipStepError(
                f"{context.order_id} - Next - Current phase is '{phase}', skipping as it"
                f" is not '{PhasesEnum.COMPLETE}'"
            )

    @override
    def process(self, context: PurchaseContext) -> None:
        pass
        # TODO create onboard ticket ticket and save ticket id in parameters

    @override
    def post_step(self, client: MPTClient, context: PurchaseContext) -> None:
        context.order = set_phase(context.order, PhasesEnum.COMPLETE)
        context.order = update_order(
            client, context.order_id, parameters=context.order["parameters"]
        )
