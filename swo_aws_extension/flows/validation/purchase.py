import logging

from mpt_extension_sdk.flows.pipeline import Pipeline, Step
from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.airtable.models import MPAStatusEnum, get_mpa_account
from swo_aws_extension.constants import (
    AccountTypesEnum,
    SupportTypesEnum,
    TransferTypesEnum,
)
from swo_aws_extension.flows.error import (
    ERR_INVALID_ACCOUNTS_FORMAT,
    ERR_SPLIT_BILLING_INVALID_CLIENT_ID_MPA_ID,
    ERR_SPLIT_BILLING_INVALID_MPA_ID,
    ERR_SPLIT_BILLING_INVALID_STATUS_MPA_ID,
    ERR_TRANSFER_TYPE,
)
from swo_aws_extension.flows.order import (
    PurchaseContext,
    reset_order_error,
)
from swo_aws_extension.flows.steps.validate import is_list_of_aws_accounts
from swo_aws_extension.flows.validation.steps import InitializeItemStep
from swo_aws_extension.parameters import (
    OrderParametersEnum,
    get_account_email,
    get_account_id,
    get_account_name,
    get_account_type,
    get_master_payer_id,
    get_transfer_type,
    reset_ordering_parameters,
    reset_ordering_parameters_error,
    set_ordering_parameter_error,
    set_support_type,
    update_ordering_parameter_constraints,
)

logger = logging.getLogger(__name__)


"""
Purchase options:

- start
  - AccountType:
    - new account:
      - require root account email
      - require account name
    - existing account:
      - require transfer type:
          - TransferType:
            - transfer with organization
                - require master_payer_id
            - transfer without organization
              - require account id
            - split billing
                - require master_payer_id
                - set support type read only
"""


class SetupNewAccountParametersConstraintsStep(Step):
    """Setups parameters visibility and constraints for purchase for new aws account."""

    def __call__(self, client: MPTClient, context: PurchaseContext, next_step):
        """Execute step."""
        if get_account_type(context.order) == AccountTypesEnum.NEW_ACCOUNT:
            parameters_to_reset = [
                OrderParametersEnum.MASTER_PAYER_ID,
                OrderParametersEnum.TRANSFER_TYPE,
                OrderParametersEnum.ACCOUNT_ID,
            ]
            context.order = reset_ordering_parameters(context.order, parameters_to_reset)
        next_step(client, context)


class SetupExistingAccountParametersConstraintsStep:
    """Setups parameters visibility and constraints for purchase for existing account."""

    def __call__(self, client: MPTClient, context: PurchaseContext, next_step):
        """Execute step."""
        if get_account_type(context.order) == AccountTypesEnum.EXISTING_ACCOUNT:
            context.order = update_ordering_parameter_constraints(
                context.order,
                OrderParametersEnum.ACCOUNT_TYPE,
                hidden=True,
                required=False,
                readonly=True,
            )
            if get_transfer_type(context.order) == TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION:
                parameters_to_reset = [
                    OrderParametersEnum.MASTER_PAYER_ID,
                    OrderParametersEnum.ROOT_ACCOUNT_EMAIL,
                    OrderParametersEnum.ACCOUNT_NAME,
                ]

            elif get_transfer_type(context.order) == TransferTypesEnum.TRANSFER_WITH_ORGANIZATION:
                parameters_to_reset = [
                    OrderParametersEnum.ACCOUNT_ID,
                    OrderParametersEnum.ROOT_ACCOUNT_EMAIL,
                    OrderParametersEnum.ACCOUNT_NAME,
                ]
            else:
                parameters_to_reset = [
                    OrderParametersEnum.ACCOUNT_ID,
                ]

            context.order = reset_ordering_parameters(context.order, parameters_to_reset)

        next_step(client, context)


class ValidateNewAccount(Step):
    """Validates if it is a new AWS account and all email and name parameters are fulfilled."""

    def __call__(self, client: MPTClient, context: PurchaseContext, next_step):
        """Execute steps."""
        if get_account_type(context.order) != AccountTypesEnum.NEW_ACCOUNT:
            next_step(client, context)
            return

        logger.info("%s - Validating new account order", context.order_id)
        required_parameters = [
            OrderParametersEnum.ROOT_ACCOUNT_EMAIL,
            OrderParametersEnum.ACCOUNT_NAME,
        ]
        required_values = [
            get_account_email(context.order),
            get_account_name(context.order),
        ]
        if any(not required_value for required_value in required_values):
            for required_param in required_parameters:
                context.order = update_ordering_parameter_constraints(
                    context.order,
                    required_param,
                    hidden=False,
                    required=True,
                    readonly=False,
                )
            return

        next_step(client, context)


class ValidateExistingAccount(Step):
    """Validates if it transfer existing account."""

    def __call__(self, client: MPTClient, context: PurchaseContext, next_step):
        """Execute step."""
        if get_account_type(context.order) != AccountTypesEnum.EXISTING_ACCOUNT:
            next_step(client, context)
            return

        logger.info("%s - Validate Existing account order", context.order_id)

        if not get_transfer_type(context.order):
            context.order = set_ordering_parameter_error(
                context.order,
                OrderParametersEnum.TRANSFER_TYPE,
                ERR_TRANSFER_TYPE.to_dict(),
            )
            return

        next_step(client, context)


class ValidateTransferWithoutOrganizationStep(Step):
    """Validates if it is a transfer without organization."""

    def __call__(self, client: MPTClient, context: PurchaseContext, next_step):
        """Execute step."""
        is_transfer_without_organization = (
            get_account_type(context.order) == AccountTypesEnum.EXISTING_ACCOUNT
            and get_transfer_type(context.order) == TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION
        )

        if not is_transfer_without_organization:
            next_step(client, context)
            return

        logger.info("%s - Validate Purchase without organization", context.order_id)

        if not context.get_account_ids():
            context.order = update_ordering_parameter_constraints(
                context.order,
                OrderParametersEnum.ACCOUNT_ID,
                hidden=False,
                required=True,
                readonly=False,
            )
            return

        multiline_account_id = get_account_id(context.order)
        if not is_list_of_aws_accounts(multiline_account_id):
            context.order = set_ordering_parameter_error(
                context.order,
                OrderParametersEnum.ACCOUNT_ID,
                ERR_INVALID_ACCOUNTS_FORMAT.to_dict(),
            )
            return

        next_step(client, context)


class ValidatePurchaseTransferWithOrganizationStep(Step):
    """Validates if it is a transfer with organization."""

    def __call__(self, client: MPTClient, context: PurchaseContext, next_step):
        """Execute step."""
        is_with_org = (
            get_account_type(context.order) == AccountTypesEnum.EXISTING_ACCOUNT
            and get_transfer_type(context.order) == TransferTypesEnum.TRANSFER_WITH_ORGANIZATION
        )

        if not is_with_org:
            next_step(client, context)
            return

        logger.info("%s - Validate Purchase WITH organization", context.order_id)

        if not get_master_payer_id(context.order):
            context.order = update_ordering_parameter_constraints(
                context.order,
                OrderParametersEnum.MASTER_PAYER_ID,
                hidden=False,
                required=True,
                readonly=False,
            )
            return
        logger.info("%s - MPA: %s", context.order_id, get_master_payer_id(context.order))

        next_step(client, context)


def is_split_billing_mpa_id_valid(context: PurchaseContext):
    """Validates the split billing MPA ID."""
    is_valid = True
    mpa_id = get_master_payer_id(context.order)

    logger.info(
        "%s - MPA: %s. Validating if already exist on Airtable for the same Client",
        context.order_id,
        mpa_id,
    )
    if not context.airtable_mpa:
        logger.error("%s - MPA: %s. MPA account not found.", context.order_id, mpa_id)
        context.order = set_ordering_parameter_error(
            context.order,
            OrderParametersEnum.MASTER_PAYER_ID,
            ERR_SPLIT_BILLING_INVALID_MPA_ID.to_dict(),
        )
        is_valid = False
    elif context.airtable_mpa.client_id != context.order.get("client", {}).get("id"):
        context.order = set_ordering_parameter_error(
            context.order,
            OrderParametersEnum.MASTER_PAYER_ID,
            ERR_SPLIT_BILLING_INVALID_CLIENT_ID_MPA_ID.to_dict(),
        )
        is_valid = False
    elif context.airtable_mpa.status not in {MPAStatusEnum.ASSIGNED, MPAStatusEnum.TRANSFERRED}:
        context.order = set_ordering_parameter_error(
            context.order,
            OrderParametersEnum.MASTER_PAYER_ID,
            ERR_SPLIT_BILLING_INVALID_STATUS_MPA_ID.to_dict(),
        )
        is_valid = False
    else:
        support_type = (
            SupportTypesEnum.PARTNER_LED_SUPPORT.value
            if context.airtable_mpa.pls_enabled
            else SupportTypesEnum.RESOLD_SUPPORT.value
        )
        context.order = set_support_type(context.order, support_type)

        context.order = update_ordering_parameter_constraints(
            context.order,
            OrderParametersEnum.SUPPORT_TYPE,
            hidden=False,
            required=False,
            readonly=True,
        )

    return is_valid


class ValidateSplitBillingStep(Step):
    """Checks split billing use case."""

    def __call__(self, client: MPTClient, context: PurchaseContext, next_step):
        """Execute step."""
        is_split_billing = (
            get_account_type(context.order) == AccountTypesEnum.EXISTING_ACCOUNT
            and get_transfer_type(context.order) == TransferTypesEnum.SPLIT_BILLING
        )
        if not is_split_billing:
            next_step(client, context)
            return
        logger.info("%s - Validate Purchase SPLIT BILLING", context.order_id)
        required_parameters = [
            OrderParametersEnum.MASTER_PAYER_ID,
            OrderParametersEnum.ROOT_ACCOUNT_EMAIL,
            OrderParametersEnum.ACCOUNT_NAME,
        ]
        required_values = [
            get_master_payer_id(context.order),
            get_account_email(context.order),
            get_account_name(context.order),
        ]
        if any(not required_value for required_value in required_values):
            for required_param in required_parameters:
                context.order = update_ordering_parameter_constraints(
                    context.order,
                    required_param,
                    hidden=False,
                    required=True,
                    readonly=False,
                )
            return
        context.airtable_mpa = get_mpa_account(get_master_payer_id(context.order))
        if is_split_billing_mpa_id_valid(context):
            next_step(client, context)


def validate_purchase_order(client: MPTClient, context: PurchaseContext):
    """Pipeline for validation of purchase order."""
    context.order = reset_order_error(context.order)
    context.order = reset_ordering_parameters_error(context.order)

    pipeline = Pipeline(
        SetupNewAccountParametersConstraintsStep(),
        SetupExistingAccountParametersConstraintsStep(),
        ValidateNewAccount(),
        ValidateExistingAccount(),
        ValidateTransferWithoutOrganizationStep(),
        ValidatePurchaseTransferWithOrganizationStep(),
        ValidateSplitBillingStep(),
        InitializeItemStep(),
    )
    pipeline.run(client, context)
    return not context.validation_succeeded, context.order
