import logging

from swo.mpt.client import MPTClient
from swo.mpt.extensions.flows.pipeline import Pipeline, Step

from swo_aws_extension.constants import AccountTypesEnum
from swo_aws_extension.flows.order import (
    OrderContext,
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
    def __call__(self, client: MPTClient, context: OrderContext, next_step):
        account_type = get_account_type(context.order)
        if account_type == AccountTypesEnum.NEW_ACCOUNT:
            logger.info("Validating new account order")
            account_email = get_account_email(context.order)
            if not account_email:
                context.order = update_ordering_parameter_constraints(
                    context.order,
                    OrderParametersEnum.PARAM_ORDER_ROOT_ACCOUNT_EMAIL,
                    hidden=False,
                    required=True,
                    readonly=False,
                )
            account_name = get_account_name(context.order)
            if not account_name:
                context.order = update_ordering_parameter_constraints(
                    context.order,
                    OrderParametersEnum.PARAM_ORDER_ACCOUNT_NAME,
                    hidden=False,
                    required=True,
                    readonly=False,
                )
        next_step(client, context)


def validate_purchase_order(client, order):
    order = reset_order_error(order)
    order = reset_ordering_parameters_error(order)

    pipeline = Pipeline(ValidateNewAccount())
    context = OrderContext(order=order)
    pipeline.run(client, context)
    return not context.validation_succeeded, context.order
