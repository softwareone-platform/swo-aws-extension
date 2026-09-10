import logging
from typing import override

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.constants import (
    PLS_SUPPORT_PLAN_COVERAGE,
    PLS_SUPPORT_PLAN_PROVIDER,
    PLS_SUPPORT_PLAN_TAM_LOCATION,
    PhasesEnum,
    SupportTypesEnum,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.errors import (
    AlreadyProcessedStepError,
    ConfigurationStepError,
    SkipStepError,
    UnexpectedStopError,
)
from swo_aws_extension.parameters import (
    get_mpa_account_id,
    get_phase,
    get_relationship_id,
    get_support_type,
    set_phase,
    set_relationship_id,
)

logger = logging.getLogger(__name__)


def build_partner_led_support_plan() -> dict:
    """Build the ``requestedSupportPlan`` union for partner-led support relationships."""
    return {
        "partnerLedSupport": {
            "coverage": PLS_SUPPORT_PLAN_COVERAGE,
            "tamLocation": PLS_SUPPORT_PLAN_TAM_LOCATION,
            "provider": PLS_SUPPORT_PLAN_PROVIDER,
        }
    }


def get_requested_support_plan(context: PurchaseContext) -> dict | None:
    """
    Return the support plan to request when creating the Partner Central relationship.

    Migrated customers already have a support plan under the SoftwareOne master payer, so
    partner-led support migration orders request the PLS plan to replace it. Regular orders
    and resold support orders keep the current behaviour and request no plan.
    """
    if not context.is_migration_order():
        return None
    if get_support_type(context.order) != SupportTypesEnum.PARTNER_LED_SUPPORT:
        return None
    return build_partner_led_support_plan()


class ConfigureAPNProgram(BasePhaseStep):
    """Handles the configuration of the APN program."""

    def __init__(self, config):
        self._config = config

    @override
    def pre_step(self, context: PurchaseContext) -> None:
        phase = get_phase(context.order)
        if phase != PhasesEnum.CONFIGURE_APN_PROGRAM:
            raise SkipStepError(
                f"{context.order_id} - Next - Current phase is '{phase}', skipping as it"
                f" is not '{PhasesEnum.CONFIGURE_APN_PROGRAM}'"
            )
        if get_relationship_id(context.order):
            context.order = set_phase(context.order, PhasesEnum.CREATE_CHANNEL_HANDSHAKE)
            raise AlreadyProcessedStepError(
                f"{context.order_id} - Next - Channel relationship already created. Continue"
            )

    @override
    def process(self, client: MPTClient, context: PurchaseContext):
        logger.info("%s - Intent - Creating channel relationship", context.order_id)

        pm_identifier = context.aws_apn_client.get_program_management_id_by_account(
            context.pm_account_id
        )
        if not pm_identifier:
            raise ConfigurationStepError(
                "Missing PMA Identifier",
                f"{context.order_id} - Error - PMA identifier not found for account"
                f" {context.pm_account_id}",
            )

        mpa_account_id = get_mpa_account_id(context.order)
        requested_support_plan = get_requested_support_plan(context)
        if requested_support_plan:
            logger.info(
                "%s - Action - Requesting partner-led support plan in the channel relationship",
                context.order_id,
            )
        try:
            relationship = context.aws_apn_client.create_relationship_in_partner_central(
                pma_identifier=pm_identifier,
                mpa_id=mpa_account_id,
                scu=context.buyer.get("externalIds", {}).get("erpCustomer", "SCU_NOT_PROVIDED"),
                requested_support_plan=requested_support_plan,
            )
        except AWSError as error:
            raise UnexpectedStopError(
                "Error creating channel relationship",
                f"{context.order_id} Error creating channel relationship: {error}",
            ) from error

        context.order = set_relationship_id(context.order, relationship["relationshipDetail"]["id"])
        logger.info(
            "%s - Action - Channel relationship created: %s",
            context.order_id,
            relationship["relationshipDetail"]["id"],
        )

    @override
    def post_step(self, client: MPTClient, context: PurchaseContext) -> None:
        context.order = set_phase(context.order, PhasesEnum.CREATE_CHANNEL_HANDSHAKE)
        context.order = update_order(
            client, context.order_id, parameters=context.order["parameters"]
        )
