import logging
import re

from mpt_extension_sdk.flows.pipeline import Step
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.flows.error import (
    ERR_INVALID_ACCOUNTS_FORMAT,
    ERR_TRANSFER_TOO_MANY_ACCOUNTS,
    ERR_TRANSFER_WITHOUT_ORG_MISSING_ACCOUNT_ID,
)
from swo_aws_extension.flows.order import (
    MPT_ORDER_STATUS_QUERYING,
    PurchaseContext,
)
from swo_aws_extension.parameters import (
    MAX_ACCOUNT_TRANSFER,
    OrderParametersEnum,
    get_account_id,
    list_ordering_parameters_with_errors,
    prepare_parameters_for_querying,
    set_ordering_parameter_error,
)

logger = logging.getLogger(__name__)


def is_list_of_aws_accounts(multiline_account_id: str) -> bool:
    """Checks if it is a list of AWS accounts."""
    if not multiline_account_id:
        return False
    pattern = r"^(?:\d{12}(?:\n+|$))+$"
    return re.fullmatch(pattern, multiline_account_id) is not None


class ValidatePurchaseTransferWithoutOrganizationStep(Step):
    """Validate if the transfer without organization is possible."""

    def __call__(self, client: MPTClient, context: PurchaseContext, next_step):
        """Run step."""
        # Checking if the step is for this type of order
        if not context.is_purchase_order():
            logger.info("%s - Skip - Order is not a purchase", context.order_id)
            next_step(client, context)
            return

        if not context.is_type_transfer_without_organization():
            logger.info(
                "%s - Skip - Order is not a transfer without organization",
                context.order_id,
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
            parameter_ids_with_errors = list_ordering_parameters_with_errors(context.order)
            context.order = prepare_parameters_for_querying(
                context.order, ignore=parameter_ids_with_errors
            )
            self.order_to_querying(client, context)
            logger.info(
                "%s - Querying - Transfer without organization has "
                "ordering parameter `orderAccountId` empty. ",
                context.order_id,
            )
            return

        multiline_account_id = get_account_id(context.order)
        if not is_list_of_aws_accounts(multiline_account_id):
            context.order = set_ordering_parameter_error(
                context.order,
                OrderParametersEnum.ACCOUNT_ID,
                ERR_INVALID_ACCOUNTS_FORMAT.to_dict(),
            )
            parameter_ids_with_errors = list_ordering_parameters_with_errors(context.order)
            context.order = prepare_parameters_for_querying(
                context.order, ignore=parameter_ids_with_errors
            )
            self.order_to_querying(client, context)
            logger.info(
                "%s - Querying - Invalid accounts ID format in `orderAccountId`. ",
                context.order_id,
            )
            return

        # Validating orderAccountId has more than 20 accounts
        if len(context.get_account_ids()) > MAX_ACCOUNT_TRANSFER:
            context.order = set_ordering_parameter_error(
                context.order,
                OrderParametersEnum.ACCOUNT_ID,
                ERR_TRANSFER_TOO_MANY_ACCOUNTS.to_dict(),
            )
            parameter_ids_with_errors = list_ordering_parameters_with_errors(context.order)
            context.order = prepare_parameters_for_querying(
                context.order, ignore=parameter_ids_with_errors
            )
            self.order_to_querying(client, context)
            logger.info(
                "%s - Querying - Transfer without organization has too many accounts",
                context.order_id,
            )
            return

        logger.info(
            "%s - Next - Transfer without organization validation completed.",
            context.order_id,
        )
        next_step(client, context)

    def order_to_querying(self, client: MPTClient, context: PurchaseContext):
        """Move order status to quering status."""
        if context.order_status != MPT_ORDER_STATUS_QUERYING:
            context.switch_order_status_to_query(client)
        else:
            update_order(
                client,
                context.order["id"],
                parameters=context.order["parameters"],
                template=context.order["template"],
            )
