import logging
from typing import Any

from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.config import Config
from swo_aws_extension.constants import FulfillmentParametersEnum
from swo_aws_extension.flows.cloud_orchestrator_utils import (
    check_onboard_status,
    get_buyer_scu,
    upgrade,
)
from swo_aws_extension.flows.jobs.migration_agreement_parameters import (
    get_agreement_parameter,
    store_agreement_parameter,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.parameters import get_execution_arn, get_mpa_account_id

logger = logging.getLogger(__name__)

# The agreement keeps every execution ARN of the upgrade in the single executionArn parameter.
EXECUTION_ARN_SEPARATOR = ","


def get_stored_execution_arns(order: dict[str, Any]) -> list[str]:
    """
    Return the services upgrade execution ARNs stored in the order agreement.

    The ARNs are stored comma-separated in the executionArn parameter; surrounding whitespace
    and empty entries are dropped, so a single ARN stored before the upgrade returned several
    executions yields a one-item list. An empty list means the upgrade has not started yet.
    """
    stored_arns = get_agreement_parameter(order, get_execution_arn) or ""
    stripped_arns = (arn.strip() for arn in stored_arns.split(EXECUTION_ARN_SEPARATOR))
    return [arn for arn in stripped_arns if arn]


def build_order_context(order: dict[str, Any]) -> PurchaseContext:
    """Build the purchase context the upgrade helpers expect from a synchronized order."""
    # from_order_data pops the agreement, buyer and seller, so the caller's order is left intact.
    return PurchaseContext.from_order_data(dict(order))


def get_upgrade_request(context: PurchaseContext) -> dict:
    """
    Build the upgrade request payload from the context.

    Cloud Orchestrator already holds the onboarded account, so the payload only carries the
    SCU and the master payer id.

    Raises:
        CloudOrchestratorMissingScuError: When the buyer SCU is missing, empty or null.
    """
    return {
        "scu": get_buyer_scu(context),
        "master_payer_id": get_mpa_account_id(context.order),
    }


def start_upgrade(config: Config, order: dict[str, Any]) -> list[str]:
    """
    Launch the services upgrade of the migrated account and return its execution ARNs.

    The account is already onboarded in Cloud Orchestrator, so the payload only carries the
    SCU and the master payer id. Cloud Orchestrator launches one execution per deployment of
    the account; an empty list means it accepted the request without returning any execution
    to follow.

    Raises:
        CloudOrchestratorError: When the upgrade cannot be started.
    """
    context = build_order_context(order)
    upgrade_payload = get_upgrade_request(context)
    return upgrade(config, upgrade_payload, str(order.get("id")))


def store_execution_arns(
    mpt_client: MPTClient, order: dict[str, Any], execution_arns: list[str]
) -> bool:
    """Store the execution ARNs comma-separated in the agreement so a retried row upgrades once."""
    return store_agreement_parameter(
        mpt_client,
        order,
        FulfillmentParametersEnum.EXECUTION_ARN,
        EXECUTION_ARN_SEPARATOR.join(execution_arns),
    )


def get_upgrade_status(config: Config, order: dict[str, Any], execution_arn: str) -> str:
    """
    Return the lower-cased status of the services upgrade execution.

    Raises:
        CloudOrchestratorError: When the status cannot be retrieved.
    """
    return check_onboard_status(config, build_order_context(order), execution_arn)
