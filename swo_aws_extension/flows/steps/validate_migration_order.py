import logging
from types import MappingProxyType
from typing import Any, override

from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.constants import (
    FulfillmentParametersEnum,
    OrderParametersEnum,
    ParamPhasesEnum,
    PhasesEnum,
)
from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.errors import SkipStepError, UnexpectedStopError
from swo_aws_extension.parameters import get_parameter, get_phase

logger = logging.getLogger(__name__)

# Parameters the Migration Orders extension prefills when it creates the quoted order,
# grouped by the parameter phase they live in. The migration flow relies on the same
# parameters as the regular flows, so all of them must carry a value before the
# fulfillment starts.
REQUIRED_MIGRATION_PARAMETERS = MappingProxyType({
    ParamPhasesEnum.ORDERING.value: (
        OrderParametersEnum.MASTER_PAYER_ACCOUNT_ID,
        OrderParametersEnum.SUPPORT_TYPE,
        OrderParametersEnum.CONTACT,
    ),
    ParamPhasesEnum.FULFILLMENT.value: (FulfillmentParametersEnum.CCO_CONTRACT_NUMBER,),
})


def get_missing_migration_data(order: dict[str, Any]) -> list[str]:
    """Return the external ids of the required migration parameters that have no value."""
    return [
        external_id.value
        for parameter_phase, external_ids in REQUIRED_MIGRATION_PARAMETERS.items()
        for external_id in external_ids
        if not get_parameter(parameter_phase, external_id.value, order).get("value")
    ]


class ValidateMigrationOrder(BasePhaseStep):
    """
    Validate that a migration order carries the data prefilled by the migration extension.

    Missing data is an operational error, not something the customer can fix: the order is
    kept in processing and the team is notified through Teams, as other steps do.
    """

    @override
    def pre_step(self, context: InitialAWSContext) -> None:
        phase = get_phase(context.order)
        if phase != PhasesEnum.CREATE_BILLING_TRANSFER_INVITATION:
            raise SkipStepError(
                f"{context.order_id} - Next - Skip migration order validation",
            )

    @override
    def process(self, client: MPTClient, context: InitialAWSContext) -> None:
        missing = get_missing_migration_data(context.order)
        if not missing:
            return
        missing_parameters = ", ".join(missing)
        logger.warning(
            "%s - Migration order is missing required parameters: %s",
            context.order_id,
            missing_parameters,
        )
        raise UnexpectedStopError(
            f"Migration order {context.order_id} is missing required data",
            f"The migration order {context.order_id} cannot be processed because the following "
            f"parameters have no value: {missing_parameters}. Please complete the order data "
            f"in the marketplace so the fulfillment can continue.",
        )

    @override
    def post_step(self, client: MPTClient, context: InitialAWSContext) -> None:
        logger.info("%s - Next - ValidateMigrationOrder completed successfully", context.order_id)
