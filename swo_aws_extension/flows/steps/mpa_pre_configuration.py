import logging

from swo.mpt.client import MPTClient
from swo.mpt.client.mpt import update_order
from swo.mpt.extensions.flows.pipeline import Step

from swo_aws_extension.constants import CREATE_ACCOUNT, PRECONFIG_MPA
from swo_aws_extension.flows.order import OrderContext
from swo_aws_extension.parameters import set_phase

logger = logging.getLogger(__name__)


class MPAPreConfiguration(Step):

    def __call__(self, client: MPTClient, context: OrderContext, next_step):
        if context.phase != PRECONFIG_MPA:
            next_step(client, context)
            return

        logger.info("Starting MPA pre-configuration. Creating AWS organization")
        context.aws_client.create_organization()

        # add logic to get next phase
        context.order = set_phase(context.order, CREATE_ACCOUNT)
        update_order(client, context.order_id, parameters=context.order["parameters"])
        logger.info("MPA pre-configuration completed successfully")
        next_step(client, context)
