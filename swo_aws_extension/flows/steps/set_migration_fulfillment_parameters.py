import logging
from types import MappingProxyType
from typing import Any, override

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.airtable.account_migration_table import AwsAccountMigrationTable
from swo_aws_extension.airtable.models import AccountMigrationRecord
from swo_aws_extension.constants import FulfillmentParametersEnum, PhasesEnum
from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.errors import SkipStepError, UnexpectedStopError
from swo_aws_extension.parameters import get_fulfillment_parameter, get_phase

logger = logging.getLogger(__name__)

# Fulfillment parameters the migration flow needs but the Migration Orders extension cannot
# set when it creates the order, mapped to the AWS Account Migration Airtable field that
# carries their value (as the attribute name of `AccountMigrationRecord`). Add a new entry
# here to copy another fulfillment parameter from the migration record.
MIGRATION_FULFILLMENT_PARAMETERS = MappingProxyType({
    FulfillmentParametersEnum.CCO_CONTRACT_NUMBER: "mpt_cco",
})


def get_unset_migration_parameters(order: dict[str, Any]) -> list[FulfillmentParametersEnum]:
    """Return the migration fulfillment parameters that have no value in the order."""
    return [
        external_id
        for external_id in MIGRATION_FULFILLMENT_PARAMETERS
        if not get_fulfillment_parameter(external_id.value, order).get("value")
    ]


def get_missing_record_values(
    record: AccountMigrationRecord, external_ids: list[FulfillmentParametersEnum]
) -> list[str]:
    """Return the external ids whose value is empty in the migration record."""
    return [
        external_id.value
        for external_id in external_ids
        if not getattr(record, MIGRATION_FULFILLMENT_PARAMETERS[external_id])
    ]


class SetMigrationFulfillmentParameters(BasePhaseStep):
    """
    Copy the fulfillment parameters of a migration order from its Airtable migration record.

    Runs once, in the createBillingTransferInvitation phase, right after the migration order
    validation. Parameters that already carry a value are left untouched, so the step is
    idempotent. A missing record or a record without the value is an operational error: the
    order stays in processing and the team is notified through Teams, as the validation does.
    """

    @override
    def pre_step(self, context: InitialAWSContext) -> None:
        phase = get_phase(context.order)
        if phase != PhasesEnum.CREATE_BILLING_TRANSFER_INVITATION:
            raise SkipStepError(
                f"{context.order_id} - Next - Skip setting migration fulfillment parameters",
            )
        if not get_unset_migration_parameters(context.order):
            raise SkipStepError(
                f"{context.order_id} - Next - Migration fulfillment parameters already set",
            )

    @override
    def process(self, client: MPTClient, context: InitialAWSContext) -> None:
        record = AwsAccountMigrationTable().get_by_order_id(context.order_id)
        if record is None:
            raise UnexpectedStopError(
                f"Migration order {context.order_id} has no migration record",
                f"The migration order {context.order_id} cannot be processed because no row of "
                f"the AWS Account Migration Airtable table is linked to it. Please link the "
                f"row to the order so the fulfillment can continue.",
            )
        unset = get_unset_migration_parameters(context.order)
        missing = get_missing_record_values(record, unset)
        if missing:
            missing_parameters = ", ".join(missing)
            raise UnexpectedStopError(
                f"Migration order {context.order_id} is missing required data",
                f"The migration order {context.order_id} cannot be processed because the "
                f"following parameters have no value in its AWS Account Migration row: "
                f"{missing_parameters}. Please complete the row so the fulfillment can "
                f"continue.",
            )
        for external_id in unset:
            parameter_value = getattr(record, MIGRATION_FULFILLMENT_PARAMETERS[external_id])
            get_fulfillment_parameter(external_id.value, context.order)["value"] = parameter_value
            logger.info(
                "%s - Action - Fulfillment parameter %s set from the migration record",
                context.order_id,
                external_id.value,
            )

    @override
    def post_step(self, client: MPTClient, context: InitialAWSContext) -> None:
        context.order = update_order(
            client, context.order_id, parameters=context.order["parameters"]
        )
