import logging

from mpt_extension_sdk.flows.pipeline import Step
from pyairtable.formulas import EQUAL, FIELD, STR_VALUE

from swo_aws_extension.airtable.models import (
    AirTableBaseInfo,
    MPAStatusEnum,
    get_master_payer_account_pool_model,
)
from swo_aws_extension.constants import SupportTypesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.assign_mpa import coppy_context_data_to_mpa_pool_model
from swo_aws_extension.parameters import get_support_type

logger = logging.getLogger(__name__)


class RegisterTransferredMPAToAirtableStep(Step):
    def exists_in_airtable(self, account_id):
        """
        Check if the MPA already exists in Airtable.
        """
        mpa_pool_model = get_master_payer_account_pool_model(AirTableBaseInfo.for_mpa_pool())
        formula = EQUAL(FIELD("Account Id"), STR_VALUE(account_id))
        response = mpa_pool_model.first(formula=formula)
        return response is not None

    def __call__(self, client, context: PurchaseContext, next_step):
        if context.airtable_mpa or self.exists_in_airtable(context.mpa_account):
            logger.info(
                f"{context.order_id} - Skip - "
                f"MPA {context.mpa_account} already registered in Airtable"
            )
            next_step(client, context)
            return
        assert context.aws_client is not None, "Missing AWS client"
        mpa_pool_model = get_master_payer_account_pool_model(AirTableBaseInfo.for_mpa_pool())
        organization = context.aws_client.describe_organization()
        context.airtable_mpa = mpa_pool_model(
            account_id=context.mpa_account,
            account_email=organization["MasterAccountEmail"],
        )
        context.airtable_mpa = coppy_context_data_to_mpa_pool_model(
            context, context.airtable_mpa, status=MPAStatusEnum.TRANSFERRED
        )
        context.airtable_mpa.pls_enabled = (
            get_support_type(context.order) == SupportTypesEnum.PARTNER_LED_SUPPORT
        )
        context.airtable_mpa.account_name = context.aws_client.account_name()
        context.airtable_mpa.save()
        logger.info(
            f"{context.order_id} - Action - "
            f"Created MPA in Airtable: {context.airtable_mpa.id} for MPA: {context.mpa_account}"
        )
        next_step(client, context)
