import logging
from functools import cache

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import (
    get_agreements_by_query,
    get_subscriptions_by_query,
    terminate_subscription,
    update_agreement,
)
from mpt_extension_sdk.mpt_http.wrap_http_error import wrap_mpt_http_error

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.config import get_config
from swo_aws_extension.constants import (
    FulfillmentParametersEnum,
    ParamPhasesEnum,
    ResponsibilityTransferStatus,
    SubscriptionStatus,
)
from swo_aws_extension.parameters import get_responsibility_transfer_id
from swo_aws_extension.swo.notifications.teams import TeamsNotificationManager
from swo_aws_extension.swo.rql.query_builder import RQLQuery

logger = logging.getLogger(__name__)


def _synchronize_agreement(mpt_client, agreement, operation_description, dry_run):
    mpa_account_id = agreement.get("externalIds", {}).get("vendor", "")
    if not mpa_account_id:
        msg = f"{agreement.get('id')} - Skipping - MPA not found"
        logger.error(msg)
        TeamsNotificationManager().send_error(operation_description, msg)
        return

    pma_account_id = agreement["authorization"].get("externalIds", {}).get("operations")
    if not pma_account_id:
        msg = f"{agreement.get('id')} - Skipping - PMA not found"
        logger.error(msg)
        TeamsNotificationManager().send_error(operation_description, msg)
        return

    try:
        accepted_transfer = get_accepted_transfer_for_account(pma_account_id, mpa_account_id)
    except Exception:
        msg = f"{agreement.get('id')} - Error occurred while fetching responsibility transfers"
        logger.exception(msg)
        TeamsNotificationManager().send_exception("Fetching responsibility transfers", msg)
        return

    if not accepted_transfer:
        msg = f"{agreement.get('id')} - agreement with an inactive transfer - terminating"
        logger.warning(msg)
        TeamsNotificationManager().send_warning(operation_description, msg)
        terminate_agreement(mpt_client, agreement, dry_run=dry_run)
        return

    sync_responsibility_transfer_id(mpt_client, agreement, accepted_transfer["Id"], dry_run=dry_run)


def synchronize_agreements(
    mpt_client: MPTClient, agreement_ids: list[str], product_ids: list[str], *, dry_run: bool
) -> None:
    """
    Synchronize all agreements.

    Args:
        mpt_client: The MPT client.
        agreement_ids: List of specific agreement IDs to synchronize.
        product_ids: List of product IDs to filter agreements.
        dry_run: Whether to perform a dry run.
    """
    product_ids = set(product_ids)
    select = "&select=parameters,subscriptions,authorization.externalIds.operations"
    if agreement_ids:
        rql_filter = (
            RQLQuery(id__in=agreement_ids)
            & RQLQuery(status="Active")
            & RQLQuery(product__id__in=product_ids)
        )
        rql_query = f"{rql_filter}{select}"

    else:
        rql_filter = RQLQuery(status="Active") & RQLQuery(product__id__in=product_ids)
        rql_query = f"{rql_filter}{select}"

    operation_description = "Synchronize AWS agreement subscriptions"
    for agreement in get_agreements_by_query(mpt_client, rql_query):
        _synchronize_agreement(mpt_client, agreement, operation_description, dry_run=dry_run)


def sync_responsibility_transfer_id(
    mpt_client: MPTClient, agreement: dict, responsibility_transfer_id: str, *, dry_run: bool
) -> None:
    """Synchronizes the PMA account ID for a given agreement."""
    if get_responsibility_transfer_id(agreement) == responsibility_transfer_id:
        return
    logger.info(
        "%s - synchronizing responsibility transfer ID: %s",
        agreement["id"],
        responsibility_transfer_id,
    )
    agreement_parameters = {
        ParamPhasesEnum.FULFILLMENT.value: [
            {
                "externalId": FulfillmentParametersEnum.RESPONSIBILITY_TRANSFER_ID.value,
                "value": responsibility_transfer_id,
            }
        ]
    }
    if dry_run:
        logger.info(
            "%s - dry run mode - skipping update with parameters: %s",
            agreement["id"],
            agreement_parameters,
        )
    else:
        try:
            update_agreement(mpt_client, agreement["id"], parameters=agreement_parameters)
        except Exception:
            msg = (
                f"{agreement['id']} - failed to update agreement with responsibility transfer ID"
                f" {responsibility_transfer_id}"
            )
            logger.exception(msg)
            TeamsNotificationManager().send_exception("Synchronize PMA account id", msg)


# TODO: SDK candidate
@wrap_mpt_http_error
def get_subscription_by_external_id(mpt_client, subscription_external_id):  # pragma: no cover
    """
    Get the first subscription for a specific external ID.

    Args:
        mpt_client: The MPT client.
        subscription_external_id: The external ID of the subscription.

    Returns:
        dict: The first subscription that matches the external ID.
    """
    select = "&select=agreement.id&limit=1"
    rql_filter = RQLQuery("externalIds.vendor").eq(subscription_external_id) & RQLQuery(
        status__in=("Active", "Updating")
    )
    rql_query = f"{rql_filter}{select}"

    response = get_subscriptions_by_query(mpt_client, rql_query)

    response.raise_for_status()
    subscriptions = response.json()
    return subscriptions["data"][0] if subscriptions["data"] else None


@cache
def get_accepted_inbound_responsibility_transfers(pma_account_id: str) -> dict:
    """Fetches ACCEPTED inbound responsibility transfers from the specified AWS client.

    Args:
        pma_account_id: The PMA account ID to query transfers from.

    Returns:
        A dict mapping source ManagementAccountId to the ACCEPTED transfer info.
    """
    config = get_config()
    aws_client = AWSClient(config, pma_account_id, config.management_role_name)
    result = {}
    for rt in aws_client.get_inbound_responsibility_transfers():
        if rt.get("Status") != ResponsibilityTransferStatus.ACCEPTED.value:
            continue
        source_account_id = rt.get("Source", {}).get("ManagementAccountId")
        if not source_account_id:
            continue
        result[source_account_id] = {"Id": rt["Id"], "Status": rt["Status"]}

    return result


def get_accepted_transfer_for_account(
    pma_account_id: str, source_management_account_id: str
) -> dict | None:
    """
    Get the ACCEPTED inbound responsibility transfer for a specific source account.

    Args:
        pma_account_id: The PMA account ID to query transfers from.
        source_management_account_id: The source ManagementAccountId to filter by.

    Returns:
        The transfer dict if found with ACCEPTED status, None otherwise.
    """
    accepted_transfers = get_accepted_inbound_responsibility_transfers(pma_account_id)
    return accepted_transfers.get(source_management_account_id)


def terminate_agreement(mpt_client: MPTClient, agreement: dict, *, dry_run) -> None:
    """Terminates agreement by terminating all its active subscriptions."""
    agreement_id = agreement["id"]
    subscription_ids = [
        sub["id"]
        for sub in agreement["subscriptions"]
        if sub["status"] != SubscriptionStatus.TERMINATED
    ]
    for subscription_id in subscription_ids:
        logger.info(
            "%s - terminating agreement due to inactive transfer - terminating subscription %s.",
            agreement_id,
            subscription_id,
        )
        if dry_run:
            logger.info(
                "%s - terminating agreement due to inactive transfer - dry run - skipping.",
                agreement_id,
            )
        else:
            try:
                terminate_subscription(
                    mpt_client,
                    subscription_id,
                    "Suspected Lost Customer",
                )
            except Exception:
                msg = (
                    f"{agreement_id} - terminating agreement due to inactive transfer -"
                    f" error terminating subscription {subscription_id}."
                )
                logger.exception(msg)
                TeamsNotificationManager().send_exception("Inactive transfer", msg)
