import logging

from mpt_extension_sdk.flows.pipeline import Step
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.constants import AccountTypesEnum, PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.parameters import get_account_type, get_phase, set_phase

logger = logging.getLogger(__name__)


class MPAPreConfiguration(Step):
    """
    Preconfiguration step for MPA.

    It configures master payer account, create organization, activate access and enables SCP.
    """
    def __call__(self, client: MPTClient, context: PurchaseContext, next_step):
        """Execute step."""
        if get_phase(context.order) != PhasesEnum.PRECONFIGURATION_MPA:
            logger.info(
                "%s - Skip - Current phase is '{get_phase(context.order)}', "
                "skipping as it is not '%s'",
                context.order_id, PhasesEnum.PRECONFIGURATION_MPA.value,
            )
            next_step(client, context)
            return

        context.aws_client.create_organization()
        context.aws_client.activate_organizations_access()
        context.aws_client.enable_scp()

        account_type = get_account_type(context.order)

        if account_type == AccountTypesEnum.NEW_ACCOUNT:
            next_phase = PhasesEnum.CREATE_ACCOUNT.value
        elif context.is_type_transfer_with_organization():
            next_phase = PhasesEnum.CREATE_SUBSCRIPTIONS.value
        else:
            next_phase = PhasesEnum.TRANSFER_ACCOUNT.value

        context.order = set_phase(context.order, next_phase)
        update_order(client, context.order_id, parameters=context.order["parameters"])
        logger.info(
            "%s - Action - '%s' completed successfully. Proceeding to next phase '%s'",
            context.order_id,
            PhasesEnum.PRECONFIGURATION_MPA.value,
            next_phase,
        )
        next_step(client, context)
