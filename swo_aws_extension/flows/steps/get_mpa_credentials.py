import logging

from swo.mpt.client import MPTClient
from swo.mpt.extensions.flows.pipeline import Step

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.flows.order import OrderContext
from swo_aws_extension.parameters import get_mpa_account_id

logger = logging.getLogger(__name__)


class GetMPACredentials(Step):
    def __init__(
            self, config, role_name
    ):
        self._config = config
        self._role_name = role_name

    def __call__(self, client: MPTClient, context: OrderContext, next_step):
        logger.info(f"Getting MPA credentials for role {self._role_name}")
        mpa_account_id = get_mpa_account_id(context.order)
        context.aws_client = AWSClient(self._config, mpa_account_id, self._role_name)
        logger.info("MPA credentials retrieved successfully")
        next_step(client, context)
