import logging

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.config import Config
from swo_aws_extension.constants import (
    PhasesEnum,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.order_utils import switch_order_status_to_process_and_notify
from swo_aws_extension.parameters import (
    get_mpa_account_id,
    set_phase,
)
from swo_aws_extension.processors.processor import Processor
from swo_aws_extension.processors.querying.helper import get_template_name, is_querying_timeout
from swo_aws_extension.swo.cloud_orchestrator.client import CloudOrchestratorClient
from swo_aws_extension.swo.cloud_orchestrator.errors import CloudOrchestratorError

logger = logging.getLogger(__name__)


class AWSCustomerRolesProcessor(Processor):
    """Process AWS customer roles timeout."""

    def __init__(self, client: MPTClient, config: Config):
        self.client = client
        self._config = config

    def can_process(self, context: PurchaseContext) -> bool:
        """Check if the order is in phase to check customer roles."""
        return context.phase == PhasesEnum.CHECK_CUSTOMER_ROLES

    def process(self, context: PurchaseContext) -> None:
        """Process AWS customer roles timeout."""
        co_client = CloudOrchestratorClient(self._config)
        mpa_account_id = get_mpa_account_id(context.order)

        try:
            bootstrap_roles_status = co_client.get_bootstrap_role_status(mpa_account_id)
        except CloudOrchestratorError as error:
            logger.info("%s - Error checking customer roles: %s", context.order_id, error)
            return

        if bootstrap_roles_status["deployed"]:
            logger.info(
                "%s - Customer roles are deployed. Updating order to processing.", context.order_id
            )
            switch_order_status_to_process_and_notify(
                self.client, context, get_template_name(context)
            )
            return

        if is_querying_timeout(context, self._config.querying_timeout_days):
            logger.info(
                "%s - Check customer roles timeout.",
                context.order_id,
            )
            logger.info(
                "%s - Updating order to processing with Phase CREATE_SUBSCRIPTION.",
                context.order_id,
            )

            switch_order_status_to_process_and_notify(
                self.client, context, get_template_name(context)
            )
            context.order = set_phase(context.order, PhasesEnum.CREATE_SUBSCRIPTION)
            context.order = update_order(
                self.client, context.order_id, parameters=context.order["parameters"]
            )
