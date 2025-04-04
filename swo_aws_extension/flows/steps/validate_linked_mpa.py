import logging

from mpt_extension_sdk.flows.pipeline import NextStep, Step
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.parameters import (
    get_phase,
    set_account_email,
    set_mpa_account_id,
    set_phase,
)

logger = logging.getLogger(__name__)


class ValidateLinkedMPAStep(Step):
    def update_organization_email(self, client, context: PurchaseContext):
        if not context.aws_client:
            raise RuntimeError("ValidateLinkedMPAStep - AWS client is not set in context")

        organization = context.aws_client.describe_organization()
        context.order = set_account_email(context.order, organization["MasterAccountEmail"])
        logger.info(
            f"{context.order_id} - Action - Organization email updated "
            f"to {organization['MasterAccountEmail']}"
        )
        context.order = set_phase(context.order, PhasesEnum.CREATE_SUBSCRIPTIONS)
        logger.info(
            f"{context.order_id} - Action - Update phase to {PhasesEnum.CREATE_SUBSCRIPTIONS}"
        )
        update_order(client, context.order_id, parameters=context.order["parameters"])

    def __call__(self, client: MPTClient, context: PurchaseContext, next_step: NextStep):
        """
        If is a transfer account:
        - Copy the master payer id to fulfillment mpa account id
        - Update the account mpa email address from AWS Organization
        - Set the phase to CREATE_SUBSCRIPTIONS
        """
        is_transfer_with_organization = (
            context.is_type_transfer_with_organization() and context.is_purchase_order()
        )
        if not is_transfer_with_organization:
            logger.info(f"{context.order_id} - Skipping - It is not a transfer with organization")
            next_step(client, context)
            return

        if get_phase(context.order) != PhasesEnum.ASSIGN_MPA:
            logger.info(
                f"{context.order_id} - Skipping - Current phase is '{get_phase(context.order)}',"
                f" skipping as it is not '{PhasesEnum.ASSIGN_MPA}'"
            )
            next_step(client, context)
            return

        if not context.mpa_account:
            logger.info(
                f"{context.order_id} - Action - MPA account is not set in context. "
                f"Setting to {context.order_master_payer_id()}"
            )
            context.order = set_mpa_account_id(
                context.order,
                context.order_master_payer_id(),
            )
            update_order(client, context.order_id, parameters=context.order["parameters"])
            logger.info(
                f"{context.order_id} - Stop - Order updated with MPA account. "
                f"Next run should have AWS access"
            )
            return

        self.update_organization_email(client, context)
        logger.info(
            f"{context.order_id} - Next - Validated Linked MPA account done."
            f" Proceeding to next step"
        )
        next_step(client, context)
