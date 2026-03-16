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


def check_onboard_status(config: Config, context: PurchaseContext, execution_arn_value: str) -> str:
    """Check the onboard status of the feature version deployment."""
    co_client = CloudOrchestratorClient(config)
    onboard_status = co_client.get_deployment_status(execution_arn_value)
    return (onboard_status.get("status") or "").lower()
