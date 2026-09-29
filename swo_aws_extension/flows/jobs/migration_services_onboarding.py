import logging
from typing import Any

from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.config import Config
from swo_aws_extension.constants import FulfillmentParametersEnum
from swo_aws_extension.flows.cloud_orchestrator_utils import (
    check_onboard_status,
    get_feature_version_onboard_request,
    onboard,
)
from swo_aws_extension.flows.jobs.migration_agreement_parameters import (
    get_agreement_parameter,
    store_agreement_parameter,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.parameters import get_execution_arn

logger = logging.getLogger(__name__)


def get_stored_execution_arn(order: dict[str, Any]) -> str | None:
    """Return the services onboarding execution ARN stored in the order agreement, if any."""
    return get_agreement_parameter(order, get_execution_arn)


def build_order_context(order: dict[str, Any]) -> PurchaseContext:
    """Build the purchase context the onboarding helpers expect from a synchronized order."""
    # from_order_data pops the agreement, buyer and seller, so the caller's order is left intact.
    return PurchaseContext.from_order_data(dict(order))


def start_onboarding(config: Config, order: dict[str, Any]) -> str:
    """
    Launch the services onboarding of the migrated account and return its execution ARN.

    The payload is the one of the OnboardServices fulfillment step. An empty ARN means Cloud
    Orchestrator accepted the request without returning the execution to follow.

    Raises:
        CloudOrchestratorError: When the onboarding cannot be started.
    """
    context = build_order_context(order)
    onboard_payload = get_feature_version_onboard_request(context)
    return onboard(config, onboard_payload, str(order.get("id")))


def store_execution_arn(mpt_client: MPTClient, order: dict[str, Any], execution_arn: str) -> bool:
    """Store the execution ARN in the agreement so a retried row does not onboard twice."""
    return store_agreement_parameter(
        mpt_client, order, FulfillmentParametersEnum.EXECUTION_ARN, execution_arn
    )


def get_onboarding_status(config: Config, order: dict[str, Any], execution_arn: str) -> str:
    """
    Return the lower-cased status of the services onboarding execution.

    Raises:
        CloudOrchestratorError: When the status cannot be retrieved.
    """
    return check_onboard_status(config, build_order_context(order), execution_arn)
