import logging

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
    prepare_parameters_for_querying,
    set_account_request_id,
    set_ordering_parameter_error,
    set_phase,
    update_ordering_parameter_constraints,
)

logger = logging.getLogger(__name__)


def manage_create_linked_account_error(
    client: MPTClient,
    context: ChangeContext,
    param_account_name: str,
    param_account_email: str,
):
    """
    Manage the error when creating a linked account.

    If the error is due to an email already
    existing, it sets the error on the parameter and switches the order to query.

    Args:
        client: The MPT client instance.
        context: The change context.
        param_account_name: The parameter ID for the account name.
        param_account_email: The parameter ID for the account email.
    """
    if context.account_creation_status.failure_reason == "EMAIL_ALREADY_EXISTS":
        logger.error(
            "%s - Error - AWS linked account creation failed: email already exists",
            context.order_id,
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
        context.order = prepare_parameters_for_querying(context.order, ignore=ignore_params)
        context.switch_order_status_to_query(
            client, OrderQueryingTemplateEnum.NEW_ACCOUNT_ROOT_EMAIL_NOT_UNIQUE
        )
        logger.info(
            "%s - Querying - Order switched to query to provide a valid email", context.order_id,
        )
        return
    logger.error(
        "%s - Stop - AWS linked account creation failed: %s",
        context.order_id, context.account_creation_status.failure_reason,
    )


def validate_linked_account_parameters(
    context: ChangeContext,
    param_account_name: str,
    param_account_email: str,
) -> tuple[bool, dict]:
    """
    Validate the parameters for creating a linked account.

    Args:
        context: The change context.
        param_account_name: The parameter ID for the account name.
        param_account_email: The parameter ID for the account email.

    Returns:
        Tuple with boolean if validation succed and updated order.
    """
    has_error = False
    if not context.root_account_email:
        logger.error("%s - Error - Email not found in order parameters", context.order_id)
        context.order = set_ordering_parameter_error(
            context.order,
            param_account_email,
            ERR_EMAIL_EMPTY.to_dict(),
        )
        has_error = True

    if not context.account_name:
        logger.error("%s - Error - Account name not found in order parameters", context.order_id)
        context.order = set_ordering_parameter_error(
            context.order,
            param_account_name,
            ERR_ACCOUNT_NAME_EMPTY.to_dict(),
        )
        has_error = True
    return has_error, context.order


class CreateInitialLinkedAccountStep(Step):
    """Create initial linked account in AWS."""
    def __call__(self, client: MPTClient, context: PurchaseContext, next_step):  # noqa: C901
        """Execute step."""
        if get_phase(context.order) != PhasesEnum.CREATE_ACCOUNT:
            logger.info(
                "%s - Skip - Current phase is '{get_phase(context.order)}', "
                "skipping as it is not '%s'",
                context.order_id, PhasesEnum.CREATE_ACCOUNT.value,
            )
            next_step(client, context)
            return

        if context.account_creation_status:
            logger.info("%s - Start - Checking linked account request status", context.order_id)
            if context.account_creation_status.status == "SUCCEEDED":
                logger.info(
                    "%s - Completed - AWS linked account created successfully", context.order_id,
                )
                context.order = set_phase(context.order, PhasesEnum.CREATE_SUBSCRIPTIONS.value)
                update_order(client, context.order_id, parameters=context.order["parameters"])
                next_step(client, context)
                return
            if context.account_creation_status.status == "IN_PROGRESS":
                logger.info("%s - Skip -AWS linked account creation in progress", context.order_id)
                return

            manage_create_linked_account_error(
                client,
                context,
                OrderParametersEnum.ACCOUNT_NAME.value,
                OrderParametersEnum.ROOT_ACCOUNT_EMAIL.value,
            )
            return

        has_error, order = validate_linked_account_parameters(
            context,
            OrderParametersEnum.ACCOUNT_NAME.value,
            OrderParametersEnum.ROOT_ACCOUNT_EMAIL.value,
        )

        if has_error:
            context.order = order
            parameter_ids_with_errors = list_ordering_parameters_with_errors(context.order)
            context.order = prepare_parameters_for_querying(
                context.order, ignore=parameter_ids_with_errors
            )
            context.switch_order_status_to_query(client)
            logger.info(
                "%s - Querying - Order switched to query. Invalid email or account name",
                context.order_id,
            )
            return

        logger.info(
            "%s - Intent - Creating initial linked account with: email=%s, name=%s",
            context.order_id, context.root_account_email, context.account_name,
        )
        try:
            linked_account = context.aws_client.create_linked_account(
                context.root_account_email, context.account_name
            )
            logger.info(
                "%s - Action - Linked account created: %s",
                context.order_id, linked_account,
            )

            context.order = set_account_request_id(context.order, linked_account.account_request_id)
            update_order(client, context.order_id, parameters=context.order["parameters"])
        except AWSError as e:
            logger.exception(
                "%s - ActionError - Error creating Linked Account.", context.order_id,
            )
            title = f"{context.order_id} - Error creating linked account"
            send_error(title, str(e))
            logger.info("%s - Stop - Unable to create linked account", context.order_id)


class AddLinkedAccountStep(Step):
    """Add linked account to the AWS account."""
    def __call__(self, client: MPTClient, context: ChangeContext, next_step):
        """Execute step."""
        if context.account_creation_status:
            logger.info("%s - Start - Checking linked account request status", context.order_id)
            if context.account_creation_status.status == "SUCCEEDED":
                # If we set the template to querying, we need to set it back to processing
                template_name = TemplateNameManager.processing(context)
                context.update_processing_template(client, template_name)
                logger.info(
                    "%s - Completed - AWS linked account created successfully", context.order_id,
                )
                next_step(client, context)
                return
            if context.account_creation_status.status == "IN_PROGRESS":
                logger.info("%s - Skip - AWS linked account creation in progress", context.order_id)
                return

            manage_create_linked_account_error(
                client,
                context,
                ChangeOrderParametersEnum.ACCOUNT_NAME.value,
                ChangeOrderParametersEnum.ROOT_ACCOUNT_EMAIL.value,
            )
            return

        has_error, order = validate_linked_account_parameters(
            context,
            ChangeOrderParametersEnum.ACCOUNT_NAME.value,
            ChangeOrderParametersEnum.ROOT_ACCOUNT_EMAIL.value,
        )

        if has_error:
            context.order = order
            parameter_ids_with_errors = list_ordering_parameters_with_errors(context.order)
            context.order = prepare_parameters_for_querying(
                context.order, ignore=parameter_ids_with_errors
            )
            context.switch_order_status_to_query(client)
            logger.info("%s - Querying - Order switched to query", context.order_id)
            return

        logger.info(
            "%s - Intent - Creating new linked account with: email=%s, name=%s",
            context.order_id, context.root_account_email, context.account_name,
        )
        linked_account = context.aws_client.create_linked_account(
            context.root_account_email, context.account_name
        )
        logger.info("%s - Action - Linked account created: %s", context.order_id, linked_account)
        context.order = set_account_request_id(context.order, linked_account.account_request_id)
        update_order(client, context.order_id, parameters=context.order["parameters"])
