import logging

from swo.mpt.client import MPTClient
from swo.mpt.extensions.flows.pipeline import Step

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.flows.order import OrderContext
from swo_aws_extension.parameters import (
    get_account_request_id,
)

logger = logging.getLogger(__name__)


class SetupContext(Step):
    def __init__(self, config, role_name):
        self._config = config
        self._role_name = role_name

    def setup_aws(self, context: OrderContext):
        if not context.mpa_account:
            raise ValueError(
                "SetupContextError - MPA account is required to setup AWS Client in context"
            )

        context.aws_client = AWSClient(
            self._config, context.mpa_account, self._role_name
        )
        logger.info(
            f"{context.order_id} - MPA credentials for {context.mpa_account} retrieved successfully"
        )

    def __call__(self, client: MPTClient, context: OrderContext, next_step):
        logger.info(
            f"{context.order_id} - SetupContext - Setting up context for the next step"
        )
        self.setup_aws(context)
        next_step(client, context)


class SetupPurchaseContext(SetupContext):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def setup_account_request_id(self, context):
        account_request_id = get_account_request_id(context.order)
        if account_request_id:
            context.account_creation_status = (
                context.aws_client.get_linked_account_status(account_request_id)
            )

    def __call__(self, client: MPTClient, context: OrderContext, next_step):
        logger.info(
            f"{context.order_id} - SetupPurchaseContext - Setting up context for the next step"
        )
        if context.mpa_account:
            self.setup_aws(context)
        self.setup_account_request_id(context)
        next_step(client, context)
