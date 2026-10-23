import logging

from swo_aws_extension.config import Config
from swo_aws_extension.constants import (
    CLOUD_ORCHESTRATOR_ONBOARDING_TYPE,
    DEFAULT_SCU,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.parameters import (
    get_mpa_account_id,
    get_support_type,
)
from swo_aws_extension.swo.cloud_orchestrator.client import CloudOrchestratorClient
from swo_aws_extension.swo.cloud_orchestrator.errors import (
    CloudOrchestratorMissingExecutionArnError,
)

logger = logging.getLogger(__name__)


def get_feature_version_onboard_request(context: PurchaseContext) -> dict:
    """Build the onboard request payload for the feature version."""
    pma = context.pm_account_id
    master_payer_id = get_mpa_account_id(context.order)
    customer_name = context.buyer.get("name")
    scu = context.buyer.get("externalIds", {}).get("erpCustomer") or DEFAULT_SCU
    support_type_value = get_support_type(context.order)
    onboarding_type = CLOUD_ORCHESTRATOR_ONBOARDING_TYPE

    return {
        "customer": customer_name,
        "scu": scu,
        "pma": pma,
        "master_payer_id": master_payer_id,
        "support_type": support_type_value,
        "onboarding_type": onboarding_type,
    }


def onboard(config: Config, onboard_payload: dict, order_id: str) -> str:
    """Onboard the customer and return the execution ARN."""
    co_client = CloudOrchestratorClient(config)
    deployed_feature_version = co_client.onboard_customer(onboard_payload)
    execution_arn = deployed_feature_version.get("execution_arn", "")
    if not execution_arn:
        logger.warning(
            "%s - Onboard response missing execution_arn: %s",
            order_id,
            deployed_feature_version,
        )
    return execution_arn


def upgrade(config: Config, upgrade_payload: dict, order_id: str) -> list[str]:
    """
    Upgrade the customer and return the execution ARNs of the deployments it launched.

    Unlike onboard, the upgrade response lists one execution per deployment of the account
    (``{"executions": [{"execution_arn": ..., "deployment_id": ...}, ...]}``). Entries without
    an execution ARN are skipped.

    Raises:
        CloudOrchestratorMissingExecutionArnError: The response has no execution ARN to poll.
    """
    co_client = CloudOrchestratorClient(config)
    upgrade_response = co_client.upgrade_customer(upgrade_payload)
    executions = upgrade_response.get("executions") or []
    execution_arns = [
        execution.get("execution_arn") for execution in executions if execution.get("execution_arn")
    ]
    if not execution_arns:
        raise CloudOrchestratorMissingExecutionArnError(upgrade_response)
    return execution_arns


def check_onboard_status(config: Config, context: PurchaseContext, execution_arn_value: str) -> str:
    """Check the onboard status of the feature version deployment."""
    co_client = CloudOrchestratorClient(config)
    onboard_status = co_client.get_deployment_status(execution_arn_value)
    return (onboard_status.get("status") or "").lower()
