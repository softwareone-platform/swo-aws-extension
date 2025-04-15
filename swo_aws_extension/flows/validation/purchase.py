import logging

from mpt_extension_sdk.flows.pipeline import Pipeline, Step
from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.constants import AccountTypesEnum, TransferTypesEnum
from swo_aws_extension.flows.error import (
    ERR_INVALID_ACCOUNTS_FORMAT,
    ERR_TRANSFER_WITH_ORG_MISSING_MPA_ID,
    ERR_TRANSFER_WITHOUT_ORG_MISSING_ACCOUNT_ID,
)
from swo_aws_extension.flows.order import (
    PurchaseContext,
    reset_order_error,
)
from swo_aws_extension.flows.steps.validate import is_list_of_aws_accounts
from swo_aws_extension.parameters import (
    OrderParametersEnum,
    get_account_email,
    get_account_id,
    get_account_name,
    get_account_type,
    get_master_payer_id,
    get_transfer_type,
    reset_ordering_parameters_error,
    set_ordering_parameter_error,
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
"""


class ValidateNewAccount(Step):
    def __call__(self, client: MPTClient, context: PurchaseContext, next_step):
        if get_account_type(context.order) != AccountTypesEnum.NEW_ACCOUNT:
            # Not new account
            context.order = update_ordering_parameter_constraints(
                context.order,
                OrderParametersEnum.ROOT_ACCOUNT_EMAIL,
                hidden=True,
                required=False,
                readonly=False,
            )
            context.order = update_ordering_parameter_constraints(
                context.order,
                OrderParametersEnum.ACCOUNT_NAME,
                hidden=True,
                required=False,
                readonly=False,
            )
            next_step(client, context)
            return

        # New account
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


class ValidateExistingAccount(Step):
    def __call__(self, client: MPTClient, context: PurchaseContext, next_step):
        if get_account_type(context.order) != AccountTypesEnum.EXISTING_ACCOUNT:
            # Not existing account
            context.order = update_ordering_parameter_constraints(
                context.order,
                OrderParametersEnum.TRANSFER_TYPE,
                hidden=True,
                required=False,
                readonly=False,
            )
            next_step(client, context)
            return
        # Existing account
        logger.info("Validate Existing account order")
        context.order = update_ordering_parameter_constraints(
            context.order,
            OrderParametersEnum.TRANSFER_TYPE,
            hidden=False,
            required=True,
            readonly=bool(get_transfer_type(context.order)),
        )
        next_step(client, context)


class ValidateTransferWithoutOrganizationStep(Step):
    def __call__(self, client: MPTClient, context: PurchaseContext, next_step):
        is_transfer_without_organization = (
            get_account_type(context.order) == AccountTypesEnum.EXISTING_ACCOUNT
            and get_transfer_type(context.order) == TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION
        )

        if not is_transfer_without_organization:
            # Not transfer without organization
            context.order = update_ordering_parameter_constraints(
                context.order,
                OrderParametersEnum.ACCOUNT_ID,
                hidden=True,
                required=False,
                readonly=False,
            )
            next_step(client, context)
            return
        logger.info("Validate Purchase without organization")
        context.order = update_ordering_parameter_constraints(
            context.order,
            OrderParametersEnum.ACCOUNT_ID,
            hidden=False,
            required=True,
            readonly=False,
        )
        if not context.get_account_ids():
            context.order = set_ordering_parameter_error(
                context.order,
                OrderParametersEnum.ACCOUNT_ID,
                ERR_TRANSFER_WITHOUT_ORG_MISSING_ACCOUNT_ID.to_dict(),
            )
            next_step(client, context)
            return

        multiline_account_id = get_account_id(context.order)
        if not is_list_of_aws_accounts(multiline_account_id):
            context.order = set_ordering_parameter_error(
                context.order,
                OrderParametersEnum.ACCOUNT_ID,
                ERR_INVALID_ACCOUNTS_FORMAT.to_dict(),
            )
            next_step(client, context)
            return

        next_step(client, context)


class ValidatePurchaseTransferWithOrganizationStep(Step):
    def __call__(self, client: MPTClient, context: PurchaseContext, next_step):
        is_with_org = (
            get_account_type(context.order) == AccountTypesEnum.EXISTING_ACCOUNT
            and get_transfer_type(context.order) == TransferTypesEnum.TRANSFER_WITH_ORGANIZATION
        )

        if not is_with_org:
            # Hide account id
            context.order = update_ordering_parameter_constraints(
                context.order,
                OrderParametersEnum.MASTER_PAYER_ID,
                hidden=True,
                required=False,
                readonly=False,
            )
            next_step(client, context)
            return
        logger.info("Validate Purchase WITH organization")
        context.order = update_ordering_parameter_constraints(
            context.order,
            OrderParametersEnum.MASTER_PAYER_ID,
            hidden=False,
            required=True,
            readonly=False,
        )
        if not get_master_payer_id(context.order):
            context.order = set_ordering_parameter_error(
                context.order,
                OrderParametersEnum.MASTER_PAYER_ID,
                ERR_TRANSFER_WITH_ORG_MISSING_MPA_ID.to_dict(),
            )
        logger.info(f"MPA: {get_master_payer_id(context.order)}")

        next_step(client, context)


def validate_purchase_order(client, context):
    context.order = reset_order_error(context.order)
    context.order = reset_ordering_parameters_error(context.order)

    pipeline = Pipeline(
        ValidateNewAccount(),
        ValidateExistingAccount(),
        ValidateTransferWithoutOrganizationStep(),
        ValidatePurchaseTransferWithOrganizationStep(),
    )
    pipeline.run(client, context)
    return not context.validation_succeeded, context.order
