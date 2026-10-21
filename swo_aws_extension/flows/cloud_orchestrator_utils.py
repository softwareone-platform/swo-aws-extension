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
    """Onboard the customer and return the execution ARN.

    Raises:
        CloudOrchestratorError: When the onboard call fails or returns no execution ARN.
    """
    co_client = CloudOrchestratorClient(config)
    execution_arn = co_client.onboard_customer(onboard_payload)["execution_arn"]
    logger.info("%s - Cloud Orchestrator onboard execution ARN: %s", order_id, execution_arn)
    return execution_arn


def upgrade(config: Config, upgrade_payload: dict, order_id: str) -> list[str]:
    """Upgrade the customer and return the execution ARNs of the deployments it launched.

    The upgrade response lists one execution per deployment of the account:
    ``{"executions": [{"execution_arn": ..., "deployment_id": ...}, ...]}``.

    Raises:
        CloudOrchestratorError: When the upgrade call fails or returns no execution ARN.
    """
    co_client = CloudOrchestratorClient(config)
    executions = co_client.upgrade_customer(upgrade_payload)["executions"]
    execution_arns = [execution["execution_arn"] for execution in executions]
    logger.info(
        "%s - Cloud Orchestrator upgrade execution ARNs: %s", order_id, ", ".join(execution_arns)
    )
    return execution_arns


def check_onboard_status(config: Config, context: PurchaseContext, execution_arn_value: str) -> str:
    """Return the lower-cased status of the deployment of the execution ARN.

    Raises:
        CloudOrchestratorError: When the status call fails or returns an unknown status.
    """
    co_client = CloudOrchestratorClient(config)
    return co_client.get_deployment_status(execution_arn_value)["status"].lower()
