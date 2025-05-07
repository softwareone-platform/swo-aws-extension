import logging

from mpt_extension_sdk.flows.pipeline import Step
from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.constants import TAG_AGREEMENT_ID, PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.parameters import get_phase

logger = logging.getLogger(__name__)


class SetupAgreementIdInAccountTagsStep(Step):
    def __call__(self, client: MPTClient, context: PurchaseContext, next_step):
        if get_phase(context.order) != PhasesEnum.CREATE_SUBSCRIPTIONS:
            logger.info(f"{context.order_id} - Skipping - Setup agreement Id Tags already done")
            next_step(client, context)
            return

        logger.info(f"{context.order_id} - Start - Setup agreement Id in account tags")
        agreement_id = context.agreement.get("id")
        accounts = context.aws_client.list_accounts()
        for account in accounts:
            account_id = account["Id"]
            account_state = account["Status"]
            if account_state != "ACTIVE":
                logger.info(
                    f"{context.order_id} - Skipping - Setup Tag Account {account_id} as"
                    f" it is not active"
                )
                continue
            context.aws_client.add_tags_for_resource(
                account_id, [{"Key": TAG_AGREEMENT_ID, "Value": agreement_id}]
            )
            logger.info(
                f"{context.order_id} - Action - Setup Tag Account {account_id} with "
                f"agreement Id {agreement_id}"
            )

        logger.info(f"{context.order_id} - Completed - Setup agreement Id in account tags")
        next_step(client, context)
