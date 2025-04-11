import logging
import re

from mpt_extension_sdk.flows.pipeline import Step
from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.flows.error import (
    ERR_INVALID_ACCOUNTS_FORMAT,
    ERR_TRANSFER_TOO_MANY_ACCOUNTS,
    ERR_TRANSFER_WITHOUT_ORG_MISSING_ACCOUNT_ID,
)
from swo_aws_extension.flows.order import PurchaseContext, switch_order_to_query
from swo_aws_extension.parameters import (
    MAX_ACCOUNT_TRANSFER,
    OrderParametersEnum,
    get_account_id,
    set_ordering_parameter_error,
)

logger = logging.getLogger(__name__)


def is_list_of_aws_accounts(multiline_account_id):
    if not multiline_account_id:
        return False
    pattern = r"^(?:\d{12}(?:\n+|$))+$"
    return re.fullmatch(pattern, multiline_account_id) is not None


class ValidatePurchaseTransferWithoutOrganizationStep(Step):
    """
    Validate if the transfer without organization is possible.
    """

    def __call__(self, client: MPTClient, context: PurchaseContext, next_step):
        # Checking if the step is for this type of order
        if not context.is_purchase_order():
            logger.info(f"{context.order_id} - Skip - Order is not a purchase")
            next_step(client, context)
            return

        if not context.is_type_transfer_without_organization():
            logger.info(
                f"{context.order_id} - Skip - Order is not a transfer without organization "
            )
            next_step(client, context)
            return

        # Validating orderAccountId is set
        if not context.get_account_ids():
            context.order = set_ordering_parameter_error(
                context.order,
                OrderParametersEnum.ACCOUNT_ID,
                ERR_TRANSFER_WITHOUT_ORG_MISSING_ACCOUNT_ID.to_dict(),
            )
            switch_order_to_query(client, context.order)
            logger.info(
                f"{context.order_id} - Querying - Transfer without organization has "
                f"ordering parameter `orderAccountId` empty. "
            )
            return

        multiline_account_id = get_account_id(context.order)
        if not is_list_of_aws_accounts(multiline_account_id):
            context.order = set_ordering_parameter_error(
                context.order,
                OrderParametersEnum.ACCOUNT_ID,
                ERR_INVALID_ACCOUNTS_FORMAT.to_dict(),
            )
            switch_order_to_query(client, context.order)
            logger.info(
                f"{context.order_id} - Querying - Invalid accounts ID format in `orderAccountId`. "
            )
            return

        # Validating orderAccountId has more than 20 accounts
        if len(context.get_account_ids()) > MAX_ACCOUNT_TRANSFER:
            context.order = set_ordering_parameter_error(
                context.order,
                OrderParametersEnum.ACCOUNT_ID,
                ERR_TRANSFER_TOO_MANY_ACCOUNTS.to_dict(),
            )
            switch_order_to_query(client, context.order)
            logger.info(
                f"{context.order_id} - Querying - Transfer without organization has "
                f"too many accounts"
            )
            return

        logger.info(
            f"{context.order_id} - Next - Transfer without organization validation completed."
        )
        next_step(client, context)
