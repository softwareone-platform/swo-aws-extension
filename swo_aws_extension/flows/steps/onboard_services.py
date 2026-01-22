import logging
from typing import override

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.aws.config import Config
from swo_aws_extension.constants import (
    PhasesEnum,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.errors import SkipStepError
from swo_aws_extension.parameters import (  # noqa: WPS235
    get_phase,
    set_phase,
)

logger = logging.getLogger(__name__)


class OnboardServices(BasePhaseStep):
    """Onboard Services step."""

    def __init__(self, config: Config):
        self._config = config

    @override
    def pre_step(self, context: PurchaseContext) -> None:
        phase = get_phase(context.order)
        if phase != PhasesEnum.ONBOARD_SERVICES:
            raise SkipStepError(
                f"{context.order_id} - Next - Current phase is '{phase}', skipping as it"
                f" is not '{PhasesEnum.ONBOARD_SERVICES}'"
            )

    @override
    def process(self, client: MPTClient, context: PurchaseContext) -> None:
        logger.info("%s - Intent - Onboarding services", context.order_id)
        # TODO implement the onboarding logic here

    @override
    def post_step(self, client: MPTClient, context: PurchaseContext) -> None:
        context.order = set_phase(context.order, PhasesEnum.CREATE_SUBSCRIPTION)
        context.order = update_order(
            client, context.order_id, parameters=context.order["parameters"]
        )
