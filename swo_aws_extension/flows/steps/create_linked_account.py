import logging

from mpt_extension_sdk.flows.pipeline import Step
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.error import (
    ERR_ACCOUNT_NAME_EMPTY,
    ERR_EMAIL_ALREADY_EXIST,
    ERR_EMAIL_EMPTY,
)
from swo_aws_extension.flows.order import (
    PurchaseContext,
    switch_order_to_query,
)
from swo_aws_extension.parameters import (
    OrderParametersEnum,
    get_account_email,
    get_account_name,
    get_phase,
    list_ordering_parameters_with_errors,
    set_account_request_id,
    set_ordering_parameter_error,
    set_ordering_parameters_to_readonly,
    set_phase,
    update_ordering_parameter_constraints,
)

logger = logging.getLogger(__name__)


class CreateLinkedAccount(Step):
    def __call__(self, client: MPTClient, context: PurchaseContext, next_step):
        are_invalid_parameters = False
        if get_phase(context.order) != PhasesEnum.CREATE_ACCOUNT:
            logger.info(
                f"Current phase is '{get_phase(context.order)}', "
                f"skipping as it is not '{PhasesEnum.CREATE_ACCOUNT}'"
            )
            next_step(client, context)
            return

        if context.account_creation_status:
            logger.info("Checking linked account request status")
            if context.account_creation_status.status == "SUCCEEDED":
                logger.info("AWS linked account created successfully")
                context.order = set_phase(context.order, PhasesEnum.CREATE_SUBSCRIPTIONS)
                update_order(client, context.order_id, parameters=context.order["parameters"])
                next_step(client, context)
                return True
            elif context.account_creation_status.status == "IN_PROGRESS":
                logger.info("AWS linked account creation in progress")
                return
            else:
                if context.account_creation_status.failure_reason == "EMAIL_ALREADY_EXISTS":
                    logger.error("AWS linked account creation failed: email already exists")
                    context.order = set_ordering_parameter_error(
                        context.order,
                        OrderParametersEnum.ROOT_ACCOUNT_EMAIL,
                        ERR_EMAIL_ALREADY_EXIST.to_dict(),
                    )

                    context.order = update_ordering_parameter_constraints(
                        context.order,
                        OrderParametersEnum.ACCOUNT_NAME,
                        readonly=False,
                        hidden=False,
                        required=False
                    )
                    context.order = set_account_request_id(context.order, "")
                    ignore_params = list_ordering_parameters_with_errors(context.order)
                    ignore_params.append(OrderParametersEnum.ACCOUNT_NAME)
                    context.order = set_ordering_parameters_to_readonly(
                        context.order, ignore=ignore_params
                    )
                    switch_order_to_query(client, context.order)
                    logger.warning("Order switched to query")
                    return
                else:
                    logger.error(
                        f"AWS linked account creation failed: "
                        f"{context.account_creation_status.failure_reason}"
                    )
                    return

        account_email = get_account_email(context.order)
        if not account_email:
            logger.error("Email not found in order parameters")
            context.order = set_ordering_parameter_error(
                context.order,
                OrderParametersEnum.ROOT_ACCOUNT_EMAIL,
                ERR_EMAIL_EMPTY.to_dict(),
            )
            are_invalid_parameters = True

        account_name = get_account_name(context.order)
        if not account_name:
            logger.error("Account name not found in order parameters")
            context.order = set_ordering_parameter_error(
                context.order,
                OrderParametersEnum.ACCOUNT_NAME,
                ERR_ACCOUNT_NAME_EMPTY.to_dict(),
            )
            are_invalid_parameters = True

        if are_invalid_parameters:
            parameter_ids_with_errors = list_ordering_parameters_with_errors(context.order)
            context.order = set_ordering_parameters_to_readonly(
                context.order, ignore=parameter_ids_with_errors
            )
            switch_order_to_query(client, context.order)
            logger.warning("Order switched to query")
            return

        logger.info(f"Creating linked account with: email={account_email}, name={account_name}")
        linked_account = context.aws_client.create_linked_account(
            account_email, account_name, context.order.get("agreement", {}).get("id")
        )
        context.order = set_account_request_id(context.order, linked_account.account_request_id)
        update_order(client, context.order_id, parameters=context.order["parameters"])
