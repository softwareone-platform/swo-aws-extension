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
    MPT_ORDER_STATUS_PROCESSING,
    MPT_ORDER_STATUS_QUERYING,
    InitialAWSContext,
    PurchaseContext,
    switch_order_to_query,
)
from swo_aws_extension.flows.template import TemplateNameManager
from swo_aws_extension.parameters import (
    OrderParametersEnum,
    get_account_request_id,
    get_phase,
    list_ordering_parameters_with_errors,
    set_ordering_parameter_error,
    set_ordering_parameters_to_readonly,
    set_phase,
)

logger = logging.getLogger(__name__)


class SetupContext(Step):
    def __init__(self, config, role_name):
        self._config = config
        self._role_name = role_name

    def setup_aws(self, context: InitialAWSContext):
        if not context.mpa_account:
            raise ValueError(
                "SetupContextError - MPA account is required to setup AWS Client in context"
            )

        context.aws_client = AWSClient(self._config, context.mpa_account, self._role_name)
        logger.info(
            f"{context.order_id} - Action - MPA credentials for {context.mpa_account} retrieved "
            f"successfully"
        )

    def init_template(self, client: MPTClient, context: InitialAWSContext):
        if context.template_name != ORDER_DEFAULT_PROCESSING_TEMPLATE:
            logger.info(
                f"{context.order_id} - Skip - Setup template: Template is not default. "
                f"Current template: `{context.template_name}`, "
                f"expected template: `{ORDER_DEFAULT_PROCESSING_TEMPLATE}`"
            )
            return

        template_name = TemplateNameManager.processing(context)

        context.update_template(client, MPT_ORDER_STATUS_PROCESSING, template_name)
        update_order(
            client,
            context.order_id,
            template=context.template,
        )

    def __call__(self, client: MPTClient, context: InitialAWSContext, next_step):
        self.init_template(client, context)
        self.setup_aws(context)
        logger.info(f"{context.order_id} - Next - SetupContext completed successfully")
        next_step(client, context)


class SetupPurchaseContext(SetupContext):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @staticmethod
    def setup_account_request_id(context):
        account_request_id = get_account_request_id(context.order)
        if account_request_id:
            context.account_creation_status = context.aws_client.get_linked_account_status(
                account_request_id
            )
            logger.info(f"{context.order_id} - Action - Setup setup_account_request_id in context")

    def __call__(self, client: MPTClient, context: InitialAWSContext, next_step):
        self.init_template(client, context)
        if context.mpa_account:
            self.setup_aws(context)
            context.airtable_mpa = get_mpa_account(context.mpa_account)
        self.setup_account_request_id(context)
        logger.info(f"{context.order_id} - Next - SetupPurchaseContext completed successfully")

        next_step(client, context)


class SetupChangeContext(SetupContext):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @staticmethod
    def setup_account_request_id(context):
        account_request_id = get_account_request_id(context.order)
        if account_request_id:
            context.account_creation_status = context.aws_client.get_linked_account_status(
                account_request_id
            )
            logger.info(f"{context.order_id} - Action - Setup setup_account_request_id in context")

    def __call__(self, client: MPTClient, context: InitialAWSContext, next_step):
        self.init_template(client, context)
        self.setup_aws(context)
        self.setup_account_request_id(context)
        logger.info(f"{context.order_id} - Next - SetupChangeContext completed successfully")
        next_step(client, context)


class SetupContextPurchaseTransferWithOrganizationStep(SetupContext):
    def __call__(self, client, context: PurchaseContext, next_step):
        """
        If not a transfer with organization purchase order, then we skip this step.

        - Set phase to TRANSFER_ACCOUNT_WITH_ORGANIZATION
        - (Validate) Check if master payer id is set, set to querying otherwise
        - Setup AWS client
        """
        self.init_template(client, context)
        if not context.is_purchase_order():
            logger.info(f"{context.order_id} - Skip - Is not a purchase order")
            next_step(client, context)
            return
        if not context.is_type_transfer_with_organization():
            logger.info(f"{context.order_id} - Skip - Is not a transfer with organization order")
            next_step(client, context)
            return

        phase = get_phase(context.order)
        if not phase:
            context.order = set_phase(context.order, PhasesEnum.TRANSFER_ACCOUNT_WITH_ORGANIZATION)

            update_order(
                client,
                context.order_id,
                parameters=context.order["parameters"],
            )
            logger.info(
                f"{context.order_id} - Action - Updated phase to {get_phase(context.order)}"
            )

        if not context.order_master_payer_id:
            context.order = set_ordering_parameter_error(
                context.order,
                OrderParametersEnum.MASTER_PAYER_ID,
                ERR_TRANSFER_WITH_ORG_MISSING_MPA_ID.to_dict(),
            )
            parameter_ids_with_errors = list_ordering_parameters_with_errors(context.order)
            context.order = set_ordering_parameters_to_readonly(
                context.order, ignore=parameter_ids_with_errors
            )
            if context.order_status != MPT_ORDER_STATUS_QUERYING:
                context.order = switch_order_to_query(client, context.order, context.buyer)
            else:
                context.order = update_order(client, context.order_id, parameters=context.order)
            logger.info(
                f"{context.order_id} - Querying - Order Master payer id is not set in "
                f"Purchase transfer with organization"
            )
            return

        if context.mpa_account:
            self.setup_aws(context)
            context.airtable_mpa = get_mpa_account(context.mpa_account)

        logger.info(
            f"{context.order_id} - Continue - Setup purchase transfer with organization completed "
            f"successfully"
        )
        next_step(client, context)


class SetupContextPurchaseTransferWithoutOrganizationStep(SetupContext):
    def __call__(self, client: MPTClient, context: InitialAWSContext, next_step):
        self.init_template(client, context)
        phase = get_phase(context.order)
        if not phase:
            context.order = set_phase(context.order, PhasesEnum.ASSIGN_MPA)
            context.order = update_order(
                client, context.order_id, parameters=context.order["parameters"]
            )
            logger.info(
                f"{context.order_id} - Action - Updated phase  to {get_phase(context.order)}"
            )
        if context.mpa_account:
            self.setup_aws(context)
            context.airtable_mpa = get_mpa_account(context.mpa_account)
        logger.info(f"{context.order_id} - Next - SetupPurchaseContext completed successfully")
        next_step(client, context)
