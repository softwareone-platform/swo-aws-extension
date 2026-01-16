import logging
from typing import override

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_agreement

from swo_aws_extension.aws.config import Config
from swo_aws_extension.constants import OrderCompletedTemplate, PhasesEnum
from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.order_utils import switch_order_status_to_complete
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.errors import SkipStepError
from swo_aws_extension.parameters import get_mpa_account_id, get_phase

logger = logging.getLogger(__name__)


class CompleteOrder(BasePhaseStep):
    """Handles the completion of an order."""

    def __init__(self, config: Config):
        self._config = config

    @override
    def pre_step(self, context: InitialAWSContext) -> None:
        phase = get_phase(context.order)
        if phase != PhasesEnum.COMPLETED:
            raise SkipStepError(
                f"{context.order_id} - Next - Current phase is '{phase}', skipping as it"
                f" is not '{PhasesEnum.COMPLETED}'"
            )

    @override
    def process(self, client: MPTClient, context: InitialAWSContext) -> None:
        template_name = OrderCompletedTemplate.PURCHASE
        mpa_id = get_mpa_account_id(context.order)

        context.agreement = update_agreement(
            client,
            context.agreement["id"],
            externalIds={"vendor": mpa_id},
        )
        logger.info(
            "%s - Action - Updated agreement external Id with Master Payer Account ID %s",
            context.order_id,
            mpa_id,
        )
        switch_order_status_to_complete(client, context, template_name)

    @override
    def post_step(self, client: MPTClient, context: InitialAWSContext) -> None:
        logger.info("%s - Completed - order has been completed successfully", context.order_id)


class CompleteTerminationOrder(BasePhaseStep):
    """Handles the completion of a termination order."""

    def __init__(self, config: Config):
        self._config = config

    @override
    def pre_step(self, context: InitialAWSContext) -> None:
        logger.info("%s - Next - Starting Terminate order completion step", context.order_id)

    @override
    def process(self, client: MPTClient, context: InitialAWSContext) -> None:
        template = OrderCompletedTemplate.TERMINATION
        switch_order_status_to_complete(client, context, template)

    @override
    def post_step(self, client: MPTClient, context: InitialAWSContext) -> None:
        logger.info(
            "%s - Completed - Termination order has been completed successfully", context.order_id
        )
