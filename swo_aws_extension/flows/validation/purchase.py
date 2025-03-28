import logging

from mpt_extension_sdk.flows.pipeline import Pipeline, Step
from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.constants import AccountTypesEnum
from swo_aws_extension.flows.order import (
    PurchaseContext,
    reset_order_error,
)
from swo_aws_extension.parameters import (
    OrderParametersEnum,
    get_account_email,
    get_account_name,
    get_account_type,
    reset_ordering_parameters_error,
    update_ordering_parameter_constraints,
)

logger = logging.getLogger(__name__)


class ValidateNewAccount(Step):
    def __call__(self, client: MPTClient, context: PurchaseContext, next_step):
        account_type = get_account_type(context.order)
        if account_type == AccountTypesEnum.NEW_ACCOUNT:
            logger.info("Validating new account order")
            account_email = get_account_email(context.order)
            if not account_email:
                context.order = update_ordering_parameter_constraints(
                    context.order,
                    OrderParametersEnum.ROOT_ACCOUNT_EMAIL,
                    hidden=False,
                    required=True,
                    readonly=False,
                )
            account_name = get_account_name(context.order)
            if not account_name:
                context.order = update_ordering_parameter_constraints(
                    context.order,
                    OrderParametersEnum.ACCOUNT_NAME,
                    hidden=False,
                    required=True,
                    readonly=False,
                )
        next_step(client, context)


def validate_purchase_order(client, context):
    context.order = reset_order_error(context.order)
    context.order = reset_ordering_parameters_error(context.order)

    pipeline = Pipeline(ValidateNewAccount())
    pipeline.run(client, context)
    return not context.validation_succeeded, context.order
