import logging
from typing import override

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.config import Config
from swo_aws_extension.constants import (
    CUSTOMER_ROLES_NOT_DEPLOYED_MESSAGE,
    CustomerRolesDeployed,
    OrderQueryingTemplateEnum,
    PhasesEnum,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.errors import QueryStepError, SkipStepError, UnexpectedStopError
from swo_aws_extension.parameters import (
    get_mpa_account_id,
    get_phase,
    set_customer_roles_deployed,
    set_phase,
)
from swo_aws_extension.swo.cloud_orchestrator.client import CloudOrchestratorClient
from swo_aws_extension.swo.cloud_orchestrator.errors import CloudOrchestratorError

logger = logging.getLogger(__name__)


class CheckCustomerRoles(BasePhaseStep):
    """Check Customer Roles step."""

    def __init__(self, config: Config) -> None:
        self._config = config

    @override
    def pre_step(self, context: PurchaseContext) -> None:
        phase = get_phase(context.order)
        if phase != PhasesEnum.CHECK_CUSTOMER_ROLES:
            raise SkipStepError(
                f"{context.order_id} - Next - Current phase is '{phase}', skipping as it"
                f" is not '{PhasesEnum.CHECK_CUSTOMER_ROLES}'"
            )

    @override
    def process(self, client: MPTClient, context: PurchaseContext) -> None:
        """Check if customer roles are deployed."""
        if not context.bootstrap_roles_status:
            co_client = CloudOrchestratorClient(self._config)
            mpa_account_id = get_mpa_account_id(context.order)
            try:
                bootstrap_roles_status = co_client.get_bootstrap_role_status(mpa_account_id)
            except CloudOrchestratorError as error:
                raise UnexpectedStopError(
                    "Error checking customer roles", f"Error details: {error}"
                ) from error
            context.bootstrap_roles_status = bootstrap_roles_status

        if context.bootstrap_roles_status["deployed"]:
            logger.info("%s - Next - Customer roles are deployed", context.order_id)
            context.order = set_customer_roles_deployed(context.order, CustomerRolesDeployed.YES)
            return

        logger.info(
            "%s - Customer roles are NOT deployed. Details: %s",
            context.order_id,
            context.bootstrap_roles_status["message"],
        )
        context.order = set_customer_roles_deployed(
            context.order, CustomerRolesDeployed.NO_DEPLOYED
        )

        raise QueryStepError(
            CUSTOMER_ROLES_NOT_DEPLOYED_MESSAGE,
            OrderQueryingTemplateEnum.WAITING_FOR_CUSTOMER_ROLES,
        )

    @override
    def post_step(self, client: MPTClient, context: PurchaseContext) -> None:
        """Hook to run after the step processing."""
        context.order = set_phase(context.order, PhasesEnum.ONBOARD_SERVICES)
        context.order = update_order(
            client, context.order_id, parameters=context.order["parameters"]
        )
