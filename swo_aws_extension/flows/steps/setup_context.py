import logging

from mpt_extension_sdk.flows.pipeline import Step
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.airtable.models import get_mpa_account
from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.constants import (
    ORDER_DEFAULT_PROCESSING_TEMPLATE,
    PhasesEnum,
)
from swo_aws_extension.flows.error import ERR_TRANSFER_WITH_ORG_MISSING_MPA_ID
from swo_aws_extension.flows.order import (
    MPT_ORDER_STATUS_QUERYING,
    InitialAWSContext,
    PurchaseContext,
)
from swo_aws_extension.flows.template import TemplateNameManager
from swo_aws_extension.parameters import (
    OrderParametersEnum,
    get_account_request_id,
    get_phase,
    list_ordering_parameters_with_errors,
    prepare_parameters_for_querying,
    set_ordering_parameter_error,
    set_phase,
)

logger = logging.getLogger(__name__)


class SetupContext(Step):
    """Initial setup context step."""

    def __init__(self, config, role_name):
        self._config = config
        self._role_name = role_name

    def setup_aws(self, context: InitialAWSContext):
        """Initialize AWS client."""
        if not context.mpa_account:
            raise ValueError(
                "SetupContextError - MPA account is required to setup AWS Client in context"
            )

        context.aws_client = AWSClient(self._config, context.mpa_account, self._role_name)
        logger.info(
            "%s - Action - MPA credentials for %s retrieved successfully",
            context.order_id,
            context.mpa_account,
        )

    def init_template(self, client: MPTClient, context: InitialAWSContext):
        """Initialize processing template."""
        if context.template_name != ORDER_DEFAULT_PROCESSING_TEMPLATE:
            logger.info(
                "%s - Skip - Setup template: Template is not default. "
                "Current template: `%s`, "
                "expected template: `%s`",
                context.order_id,
                context.template_name,
                ORDER_DEFAULT_PROCESSING_TEMPLATE,
            )
            return

        template_name = TemplateNameManager.processing(context)
        context.update_processing_template(client, template_name)

    def setup_account_request_id(self, context):
        """Fetches linked account status."""
        account_request_id = get_account_request_id(context.order)
        if account_request_id:
            context.account_creation_status = context.aws_client.get_linked_account_status(
                account_request_id
            )
            logger.info(
                "%s - Action - Setup setup_account_request_id in context: %s",
                context.order_id,
                context.account_creation_status,
            )

    def __call__(self, client: MPTClient, context: InitialAWSContext, next_step):
        """Execute step."""
        self.init_template(client, context)
        self.setup_aws(context)
        logger.info("%s - Next - SetupContext completed successfully", context.order_id)
        next_step(client, context)


class SetupPurchaseContext(SetupContext):
    """Setup Context for purchase order."""

    def __call__(self, client: MPTClient, context: InitialAWSContext, next_step):
        """Execute step."""
        self.init_template(client, context)
        if context.mpa_account:
            self.setup_aws(context)
            context.airtable_mpa = get_mpa_account(context.mpa_account)
        self.setup_account_request_id(context)
        logger.info("%s - Next - SetupPurchaseContext completed successfully", context.order_id)

        next_step(client, context)


class SetupChangeContext(SetupContext):
    """Setup context for change order."""

    def __call__(self, client: MPTClient, context: InitialAWSContext, next_step):
        """Execute step."""
        self.init_template(client, context)
        self.setup_aws(context)
        self.setup_account_request_id(context)
        logger.info("%s - Next - SetupChangeContext completed successfully", context.order_id)
        next_step(client, context)


class SetupContextPurchaseTransferWithOrganizationStep(SetupContext):
    """Setups context for purchase case with organization."""

    def __call__(self, client, context: PurchaseContext, next_step):  # noqa: C901
        """
        If not a transfer with organization purchase order, then we skip this step.

        - Set phase to TRANSFER_ACCOUNT_WITH_ORGANIZATION
        - (Validate) Check if master payer id is set, set to querying otherwise
        - Setup AWS client
        """
        self.init_template(client, context)
        if not context.is_purchase_order():
            logger.info("%s - Skip - Is not a purchase order", context.order_id)
            next_step(client, context)
            return
        if not context.is_type_transfer_with_organization():
            logger.info("%s - Skip - Is not a transfer with organization order", context.order_id)
            next_step(client, context)
            return

        phase = get_phase(context.order)
        if not phase:
            context.order = set_phase(
                context.order, PhasesEnum.TRANSFER_ACCOUNT_WITH_ORGANIZATION.value
            )

            update_order(
                client,
                context.order_id,
                parameters=context.order["parameters"],
            )
            logger.info(
                "%s - Action - Updated phase to {get_phase(context.order)}",
                context.order_id,
            )

        if not context.order_master_payer_id:
            context.order = set_ordering_parameter_error(
                context.order,
                OrderParametersEnum.MASTER_PAYER_ID,
                ERR_TRANSFER_WITH_ORG_MISSING_MPA_ID.to_dict(),
            )
            parameter_ids_with_errors = list_ordering_parameters_with_errors(context.order)
            context.order = prepare_parameters_for_querying(
                context.order, ignore=parameter_ids_with_errors
            )
            if context.order_status != MPT_ORDER_STATUS_QUERYING:
                context.switch_order_status_to_query(client)
            else:
                context.order = update_order(client, context.order_id, parameters=context.order)
            logger.info(
                "%s - Querying - Order Master payer id is not set in "
                "Purchase transfer with organization",
                context.order_id,
            )
            return

        if context.mpa_account:
            self.setup_aws(context)
            context.airtable_mpa = get_mpa_account(context.mpa_account)

        logger.info(
            "%s - Continue - Setup purchase transfer with organization completed successfully",
            context.order_id,
        )
        next_step(client, context)


class SetupContextPurchaseTransferWithoutOrganizationStep(SetupContext):
    """Setup context for purchases to transfer without organization."""

    def __call__(self, client: MPTClient, context: InitialAWSContext, next_step):
        """Execute step."""
        self.init_template(client, context)
        phase = get_phase(context.order)
        if not phase:
            context.order = set_phase(context.order, PhasesEnum.ASSIGN_MPA.value)
            context.order = update_order(
                client, context.order_id, parameters=context.order["parameters"]
            )
            logger.info(
                "%s - Action - Updated phase  to %s",
                context.order_id,
                get_phase(context.order),
            )
        if context.mpa_account:
            self.setup_aws(context)
            context.airtable_mpa = get_mpa_account(context.mpa_account)
        logger.info("%s - Next - SetupPurchaseContext completed successfully", context.order_id)
        next_step(client, context)


class SetupTerminateContextStep(SetupContext):
    """Setup context for termination orders."""

    def __call__(self, client: MPTClient, context: InitialAWSContext, next_step):
        """Execute step."""
        self.init_template(client, context)
        self.setup_aws(context)
        logger.info(
            "%s - Next - SetupTerminateContextStep completed successfully",
            context.order_id,
        )
        next_step(client, context)
