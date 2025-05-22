import functools
import logging
from datetime import date

from mpt_extension_sdk.flows.pipeline import Step
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.constants import OrderQueryingTemplateEnum, PhasesEnum
from swo_aws_extension.flows.error import (
    ERR_ACCOUNT_NAME_EMPTY,
    ERR_EMAIL_ALREADY_EXIST,
    ERR_EMAIL_EMPTY,
)
from swo_aws_extension.flows.order import (
    ChangeContext,
    PurchaseContext,
)
from swo_aws_extension.flows.template import TemplateNameManager
from swo_aws_extension.notifications import send_error
from swo_aws_extension.parameters import (
    ChangeOrderParametersEnum,
    OrderParametersEnum,
    get_phase,
    list_ordering_parameters_with_errors,
    set_account_request_id,
    set_ordering_parameter_error,
    set_ordering_parameters_to_readonly,
    set_phase,
    update_ordering_parameter_constraints,
)

logger = logging.getLogger(__name__)


@functools.cache
def notify_error_creating_linked_account(order_id, error, _date):
    title = f"{order_id} - Error creating linked account"
    send_error(title, error)


def manage_create_linked_account_error(client, context, param_account_name, param_account_email):
    """
    Manage the error when creating a linked account. If the error is due to an email already
    existing, it sets the error on the parameter and switches the order to query.
    Args:
        client (MPTClient): The MPT client instance.
        context (InitialContext): The change context.
        param_account_name (str): The parameter ID for the account name.
        param_account_email (str): The parameter ID for the account email.
    """
    if context.account_creation_status.failure_reason == "EMAIL_ALREADY_EXISTS":
        logger.error(
            f"{context.order_id} - Error - AWS linked account creation failed: email already exists"
        )
        context.order = set_ordering_parameter_error(
            context.order,
            param_account_email,
            ERR_EMAIL_ALREADY_EXIST.to_dict(),
        )

        context.order = update_ordering_parameter_constraints(
            context.order,
            param_account_name,
            readonly=False,
            hidden=False,
            required=False,
        )

        context.order = set_account_request_id(context.order, "")
        ignore_params = list_ordering_parameters_with_errors(context.order)
        ignore_params.append(param_account_name)
        context.order = set_ordering_parameters_to_readonly(context.order, ignore=ignore_params)
        context.switch_order_status_to_query(
            client, OrderQueryingTemplateEnum.NEW_ACCOUNT_ROOT_EMAIL_NOT_UNIQUE
        )
        logger.info(
            f"{context.order_id} - Querying - Order switched to query to provide a valid email"
        )
        return
    logger.error(
        f"{context.order_id} - Stop - AWS linked account creation failed: "
        f"{context.account_creation_status.failure_reason}"
    )


def validate_linked_account_parameters(context, param_account_name, param_account_email):
    """
    Validate the parameters for creating a linked account.
    Args:
        context (InitialContext): The change context.
        param_account_name (str): The parameter ID for the account name.
        param_account_email (str): The parameter ID for the account email.
    Returns:
        bool: True if there are errors, False otherwise.
        dict: The updated order dictionary.
    """
    has_error = False
    if not context.root_account_email:
        logger.error(f"{context.order_id} - Error - Email not found in order parameters")
        context.order = set_ordering_parameter_error(
            context.order,
            param_account_email,
            ERR_EMAIL_EMPTY.to_dict(),
        )
        has_error = True

    if not context.account_name:
        logger.error(f"{context.order_id} - Error - Account name not found in order parameters")
        context.order = set_ordering_parameter_error(
            context.order,
            param_account_name,
            ERR_ACCOUNT_NAME_EMPTY.to_dict(),
        )
        has_error = True
    return has_error, context.order


class CreateInitialLinkedAccountStep(Step):
    def __call__(self, client: MPTClient, context: PurchaseContext, next_step):
        if get_phase(context.order) != PhasesEnum.CREATE_ACCOUNT:
            logger.info(
                f"{context.order_id} - Skip - Current phase is '{get_phase(context.order)}', "
                f"skipping as it is not '{PhasesEnum.CREATE_ACCOUNT}'"
            )
            next_step(client, context)
            return

        if context.account_creation_status:
            logger.info(f"{context.order_id} - Start - Checking linked account request status")
            if context.account_creation_status.status == "SUCCEEDED":
                logger.info(
                    f"{context.order_id} - Completed - AWS linked account created successfully"
                )
                context.order = set_phase(context.order, PhasesEnum.CREATE_SUBSCRIPTIONS)
                update_order(client, context.order_id, parameters=context.order["parameters"])
                next_step(client, context)
                return
            elif context.account_creation_status.status == "IN_PROGRESS":
                logger.info(f"{context.order_id} - Skip -AWS linked account creation in progress")
                return
            else:
                manage_create_linked_account_error(
                    client,
                    context,
                    OrderParametersEnum.ACCOUNT_NAME,
                    OrderParametersEnum.ROOT_ACCOUNT_EMAIL,
                )
                return

        has_error, order = validate_linked_account_parameters(
            context, OrderParametersEnum.ACCOUNT_NAME, OrderParametersEnum.ROOT_ACCOUNT_EMAIL
        )

        if has_error:
            context.order = order
            parameter_ids_with_errors = list_ordering_parameters_with_errors(context.order)
            context.order = set_ordering_parameters_to_readonly(
                context.order, ignore=parameter_ids_with_errors
            )
            context.switch_order_status_to_query(client)
            logger.info(
                f"{context.order_id} - Querying - Order switched to query. Invalid email or "
                f"account name"
            )
            return

        logger.info(
            f"{context.order_id} - Intent - Creating initial linked account with: "
            f"email={context.root_account_email}, name={context.account_name}"
        )
        try:
            linked_account = context.aws_client.create_linked_account(
                context.root_account_email, context.account_name
            )
            logger.info(f"{context.order_id} - Action - Linked account created: {linked_account}")

            context.order = set_account_request_id(context.order, linked_account.account_request_id)
            update_order(client, context.order_id, parameters=context.order["parameters"])
        except AWSError as e:
            logger.info(f"{context.order_id} - ActionError - Error creating Linked Account: {e}")
            notify_error_creating_linked_account(
                context.order_id,
                str(e),
                date.today().isoformat(),
            )
            logger.info(f"{context.order_id} - Stop - Unable to create linked account")


class AddLinkedAccountStep(Step):
    def __call__(self, client: MPTClient, context: ChangeContext, next_step):
        if context.account_creation_status:
            logger.info(f"{context.order_id} - Start - Checking linked account request status")
            if context.account_creation_status.status == "SUCCEEDED":
                # If we set the template to querying, we need to set it back to processing
                template_name = TemplateNameManager.processing(context)
                context.update_processing_template(client, template_name)
                logger.info(
                    f"{context.order_id} - Completed - AWS linked account created successfully"
                )
                next_step(client, context)
                return
            elif context.account_creation_status.status == "IN_PROGRESS":
                logger.info(f"{context.order_id} - Skip - AWS linked account creation in progress")
                return
            else:
                manage_create_linked_account_error(
                    client,
                    context,
                    ChangeOrderParametersEnum.ACCOUNT_NAME,
                    ChangeOrderParametersEnum.ROOT_ACCOUNT_EMAIL,
                )
                return

        has_error, order = validate_linked_account_parameters(
            context,
            ChangeOrderParametersEnum.ACCOUNT_NAME,
            ChangeOrderParametersEnum.ROOT_ACCOUNT_EMAIL,
        )

        if has_error:
            context.order = order
            parameter_ids_with_errors = list_ordering_parameters_with_errors(context.order)
            context.order = set_ordering_parameters_to_readonly(
                context.order, ignore=parameter_ids_with_errors
            )
            context.switch_order_status_to_query(client)
            logger.info(f"{context.order_id} - Querying - Order switched to query")
            return

        logger.info(
            f"{context.order_id} - Intent - Creating new linked account with: "
            f"email={context.root_account_email}, name={context.account_name}"
        )
        linked_account = context.aws_client.create_linked_account(
            context.root_account_email, context.account_name
        )
        logger.info(f"{context.order_id} - Action - Linked account created: {linked_account}")
        context.order = set_account_request_id(context.order, linked_account.account_request_id)
        update_order(client, context.order_id, parameters=context.order["parameters"])
