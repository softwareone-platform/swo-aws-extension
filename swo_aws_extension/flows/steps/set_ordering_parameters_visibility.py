import logging
from typing import override

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.constants import OrderParametersEnum, PhasesEnum
from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.errors import SkipStepError
from swo_aws_extension.parameters import (
    get_ordering_parameter,
    get_phase,
    set_order_parameter_constraints,
)

logger = logging.getLogger(__name__)

# Ordering parameters the Migration Orders extension sends with the migration order.
MIGRATION_ORDERING_PARAMETERS = (
    OrderParametersEnum.ACCOUNT_TYPE,
    OrderParametersEnum.MASTER_PAYER_ACCOUNT_ID,
    OrderParametersEnum.SUPPORT_TYPE,
    OrderParametersEnum.CONTACT,
)


def get_hidden_ordering_parameters(order: dict) -> list[OrderParametersEnum]:
    """Return the migration ordering parameters that are hidden in the order."""
    return [
        external_id
        for external_id in MIGRATION_ORDERING_PARAMETERS
        if (get_ordering_parameter(external_id, order).get("constraints") or {}).get("hidden")
    ]


class SetOrderingParametersVisibility(BasePhaseStep):
    """
    Show the ordering parameters sent with a migration order.

    The Migration Orders extension creates the order in the Quoted status, so the draft
    validation never makes its ordering parameters visible. The vendor-only migration
    parameter stays hidden.
    """

    @override
    def pre_step(self, context: InitialAWSContext) -> None:
        phase = get_phase(context.order)
        if phase != PhasesEnum.CREATE_BILLING_TRANSFER_INVITATION:
            raise SkipStepError(
                f"{context.order_id} - Next - Skip setting ordering parameters visibility",
            )
        if not get_hidden_ordering_parameters(context.order):
            raise SkipStepError(
                f"{context.order_id} - Next - Ordering parameters already visible",
            )

    @override
    def process(self, client: MPTClient, context: InitialAWSContext) -> None:
        for external_id in get_hidden_ordering_parameters(context.order):
            context.order = set_order_parameter_constraints(
                context.order, external_id, constraints={"hidden": False}
            )
            logger.info(
                "%s - Action - Ordering parameter %s set visible",
                context.order_id,
                external_id.value,
            )

    @override
    def post_step(self, client: MPTClient, context: InitialAWSContext) -> None:
        context.order = update_order(
            client, context.order_id, parameters=context.order["parameters"]
        )
