import logging

from mpt_extension_sdk.flows.pipeline import Step
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.error import ERR_TRANSFER_WITH_ORG_MISSING_MPA_ID
from swo_aws_extension.flows.order import InitialAWSContext, PurchaseContext, switch_order_to_query
from swo_aws_extension.parameters import (
    OrderParametersEnum,
    get_account_request_id,
    get_phase,
    set_ordering_parameter_error,
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

    def __call__(self, client: MPTClient, context: InitialAWSContext, next_step):
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
        if context.mpa_account:
            self.setup_aws(context)
        self.setup_account_request_id(context)
        logger.info(f"{context.order_id} - Next - SetupPurchaseContext completed successfully")
        next_step(client, context)


class SetupContextPurchaseTransferWithOrganizationStep(SetupContext):
    def __call__(self, client, context: PurchaseContext, next_step):
        """
        If not a transfer with organization purchase order, then we skip this step.

        - Set phase to TRANSFER_ACCOUNT_WITH_ORGANIZATION
        - (Validate) Check if master payer id is set, set to querying otherwise
        - Setup AWS client
        """
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
            update_order(client, context.order_id, parameters=context.order["parameters"])
            logger.info(
                f"{context.order_id} - Action - Updated phase to {get_phase(context.order)}"
            )

        if not context.order_master_payer_id:
            context.order = set_ordering_parameter_error(
                context.order,
                OrderParametersEnum.MASTER_PAYER_ID,
                ERR_TRANSFER_WITH_ORG_MISSING_MPA_ID.to_dict(),
            )
            context.order = switch_order_to_query(client, context.order)
            logger.info(
                f"{context.order_id} - Querying - Order Master payer id is not set in "
                f"Purchase transfer with organization"
            )
            return

        if context.mpa_account:
            self.setup_aws(context)

        logger.info(
            f"{context.order_id} - Continue - Setup purchase transfer with organization completed "
            f"successfully"
        )
        next_step(client, context)


class SetupContextPurchaseTransferWithoutOrganizationStep(SetupContext):
    def __call__(self, client: MPTClient, context: InitialAWSContext, next_step):
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
        logger.info(f"{context.order_id} - Next - SetupPurchaseContext completed successfully")
        next_step(client, context)
