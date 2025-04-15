import logging

from mpt_extension_sdk.flows.pipeline import Step
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.constants import AccountTypesEnum, PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.parameters import get_account_type, get_phase, set_phase

logger = logging.getLogger(__name__)


class MPAPreConfiguration(Step):
    def __call__(self, client: MPTClient, context: PurchaseContext, next_step):
        if get_phase(context.order) != PhasesEnum.PRECONFIGURATION_MPA:
            logger.info(
                f"Current phase is '{get_phase(context.order)}', "
                f"skipping as it is not '{PhasesEnum.PRECONFIGURATION_MPA}'"
            )
            next_step(client, context)
            return

        context.aws_client.create_organization()
        context.aws_client.activate_organizations_access()
        context.aws_client.enable_scp()

        account_type = get_account_type(context.order)

        if account_type == AccountTypesEnum.NEW_ACCOUNT:
            next_phase = PhasesEnum.CREATE_ACCOUNT
        else:
            next_phase = PhasesEnum.TRANSFER_ACCOUNT

        context.order = set_phase(context.order, next_phase)
        update_order(client, context.order_id, parameters=context.order["parameters"])
        logger.info(
            f"'{PhasesEnum.PRECONFIGURATION_MPA}' completed successfully. "
            f"Proceeding to next phase '{next_phase}'"
        )
        next_step(client, context)
