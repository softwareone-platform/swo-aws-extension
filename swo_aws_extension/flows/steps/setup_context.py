import logging

from swo.mpt.client import MPTClient
from swo.mpt.extensions.flows.pipeline import Step

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.flows.order import OrderContext
from swo_aws_extension.parameters import (
    get_account_request_id,
    get_mpa_account_id,
)

logger = logging.getLogger(__name__)


class SetupContext(Step):
    def __init__(self, config, role_name):
        self._config = config
        self._role_name = role_name

    def __call__(self, client: MPTClient, context: OrderContext, next_step):
        logger.info("Setting up context for the next step")
        mpa_account_id = get_mpa_account_id(context.order)

        if mpa_account_id:
            context.aws_client = AWSClient(
                self._config, mpa_account_id, self._role_name
            )
            logger.info("MPA credentials retrieved successfully")

        account_request_id = get_account_request_id(context.order)
        if account_request_id:
            context.account_creation_status = (
                context.aws_client.get_linked_account_status(account_request_id)
            )

        next_step(client, context)
