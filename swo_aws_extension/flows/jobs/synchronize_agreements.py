import logging
from datetime import UTC, datetime

from dateutil.relativedelta import relativedelta
from mpt_extension_sdk.mpt_http.mpt import (
    create_agreement_subscription,
    get_agreements_by_query,
    get_product_items_by_skus,
    update_agreement_subscription,
)
from mpt_extension_sdk.mpt_http.utils import find_first
from mpt_extension_sdk.mpt_http.wrap_http_error import wrap_mpt_http_error

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.constants import (
    AWS_ITEMS_SKUS,
    MPT_DATE_TIME_FORMAT,
    SWO_EXTENSION_MANAGEMENT_ROLE,
    SubscriptionStatusEnum,
)
from swo_aws_extension.flows.steps.finops import create_finops_entitlement
from swo_aws_extension.notifications import send_error
from swo_aws_extension.parameters import FulfillmentParametersEnum
from swo_finops_client.client import get_ffc_client
from swo_rql import RQLQuery

logger = logging.getLogger(__name__)


def synchronize_agreements(mpt_client, config, agreement_ids, dry_run, product_ids):
    """
    Synchronize all agreements.

    Args:
        mpt_client: The MPT client.
        config: The configuration object.
        agreement_ids: List of specific agreement IDs to synchronize.
        dry_run: Whether to perform a dry run.
        product_ids: List of product IDs to filter agreements.
    """
    product_ids = list(set(product_ids))
    select = "&select=lines,parameters,subscriptions,subscriptions.lines,product,listing"
    if agreement_ids:
        rql_filter = (
            RQLQuery(id__in=agreement_ids)
            and RQLQuery(status="Active")
            and RQLQuery(product__id__in=product_ids)
        )
        rql_query = f"{rql_filter}{select}"

    else:
        rql_filter = RQLQuery(status="Active") and RQLQuery(product__id__in=product_ids)
        rql_query = f"{rql_filter}{select}"

    agreements = get_agreements_by_query(mpt_client, rql_query)

    for agreement in agreements:
        try:
            mpa_account = agreement.get("externalIds", {}).get("vendor", "")
            if not mpa_account:
                logger.error(f"{agreement.get('id')} - Skipping - MPA not found")
                continue

            aws_client = AWSClient(config, mpa_account, SWO_EXTENSION_MANAGEMENT_ROLE)
            sync_agreement_subscriptions(mpt_client, aws_client, agreement, dry_run)
        except Exception as e:
            logger.exception(f"{agreement.get('id')} - Failed to synchronize agreement: {e}")
            send_error(
                "Synchronize AWS agreement subscriptions",
                f"Failed to synchronize agreement {agreement.get('id')}: {e}",
            )
            continue


def _get_active_accounts(aws_client, agreement_id, mpa_account_id):
    """
    Get active accounts.
    Args:
        aws_client: The AWS client.
        agreement_id: The agreement ID.
        mpa_account_id: The MPA account ID.
    Returns:
        List of active accounts
    """

    accounts = aws_client.list_accounts()
    active_accounts = []
    for account in accounts:
        # Management account will not be synchronized
        if account["Id"] == mpa_account_id:
            continue
        if account["Status"] != "ACTIVE":
            logger.info(
                f"{agreement_id} - Skipping - Import Account {account["Id"]} as it is not active"
            )
            continue

        active_accounts.append(account)
    return active_accounts


def check_existing_subscription_items(mpt_client, items, subscription, agreement_id):
    """
    Check and update the items in an existing subscription.
    Args:
        mpt_client: The MPT client.
        items: List of items to check.
        subscription: The subscription to check.
        agreement_id: The agreement ID.
    """

    purchased_skus = [
        line["item"]["externalIds"]["vendor"] for line in subscription.get("lines", [])
    ]
    skus_to_add = [sku for sku in AWS_ITEMS_SKUS if sku not in purchased_skus]
    skus_to_delete = [sku for sku in purchased_skus if sku not in AWS_ITEMS_SKUS]
    if skus_to_add:
        for sku_to_add in skus_to_add:
            subscription["lines"].append(
                {
                    "item": find_first(
                        lambda item, sku=sku_to_add: item["externalIds"]["vendor"] == sku,
                        items,
                    ),
                    "quantity": 1,
                }
            )
        subscription = update_agreement_subscription(
            mpt_client, subscription.get("id"), lines=subscription.get("lines")
        )
        logger.info(
            f"{agreement_id} - Action - Added items {skus_to_add} to subscription"
            f" {subscription.get('id')}"
        )

    if skus_to_delete:
        lines = []
        for line in subscription.get("lines", []):
            if line["item"]["externalIds"]["vendor"] not in skus_to_delete:
                lines.append(line)
        subscription = update_agreement_subscription(
            mpt_client, subscription.get("id"), lines=lines
        )
        logger.info(
            f"{agreement_id} - Action - Removed items {skus_to_delete} from subscription "
            f"{subscription.get('id')}"
        )


def has_split_billing(mpt_client, external_id):
    """
    Check if there are multiple active agreements for the same external ID.
    Args:
        mpt_client: The MPT client.
        external_id: The external ID to check.

    Returns:
        bool: True if there are multiple active agreements, False otherwise.
    """
    rql_query = (
        f"and(in(status,(Active,Updating,Provisioning)),eq(externalIds.vendor,{external_id})"
    )

    return len(get_agreements_by_query(mpt_client, rql_query)) > 1


@wrap_mpt_http_error
def get_subscription_by_external_id(mpt_client, subscription_external_id):  # pragma: no cover
    """
    Get the first subscription for a specific external ID.
    Args:
        mpt_client: The MPT client.
        subscription_external_id: The external ID of the subscription.

    Returns:
        dict: The first subscription that matches the external ID.
    TODO: SDK candidate
    """
    response = mpt_client.get(
        f"/commerce/subscriptions?eq(externalIds.vendor,{subscription_external_id})"
        f"&in(status,(Active,Updating))"
        f"&select=agreement.id&limit=1"
    )

    response.raise_for_status()
    subscriptions = response.json()
    return subscriptions["data"][0] if subscriptions["data"] else None


def _synchronize_new_accounts(mpt_client, agreement, active_accounts, dry_run):
    """
    Synchronize new AWS linked accounts for a specific agreement.
    Args:
        mpt_client: The MPT client.
        agreement: The agreement to synchronize.
        active_accounts: List of accounts associated with the agreement.
        dry_run: Whether to perform a dry run.

    """
    for account in active_accounts:
        account_id = account["Id"]
        account_email = account["Email"]
        account_name = account["Name"]
        try:
            existing_subscription = find_first(
                lambda sub, acc_id=account_id: sub.get("externalIds", {}).get("vendor") == acc_id
                and sub.get("status") == "Active",
                agreement["subscriptions"],
            )
            items = get_product_items_by_skus(
                mpt_client, agreement.get("product").get("id"), AWS_ITEMS_SKUS
            )

            if not items:
                logger.error(
                    f"{agreement.get("id")} - Failed to get product items with "
                    f"skus {AWS_ITEMS_SKUS}"
                )
                continue

            if existing_subscription:
                check_existing_subscription_items(
                    mpt_client, items, existing_subscription, agreement.get("id")
                )
                logger.info(
                    f"{agreement.get('id')} - Next - Subscription for {account_id} "
                    f"({existing_subscription['id']}) synchronized"
                )
                continue

            if has_split_billing(mpt_client, agreement.get("externalIds", {}).get("vendor")):
                subscription_by_external_id = get_subscription_by_external_id(
                    mpt_client, account_id
                )
                if subscription_by_external_id:
                    logger.info(
                        f"{agreement.get('id')} - Skipping - Account {account_id} already exists "
                        f"for Subscription {subscription_by_external_id['id']} in agreement "
                        f"{subscription_by_external_id['agreement']['id']}"
                    )
                    continue
                logger.error(
                    f"{agreement.get("id")} - Error - {account_id} is not linked to any "
                    f"agreement subscription and split billing has been detected"
                )
                send_error(
                    "Synchronize AWS agreement subscriptions - New linked account detected",
                    f"{agreement.get("id")} - Linked Account {account_id} is not linked to any "
                    f"subscription and split billing has been detected. This account will not be "
                    f"synchronized.",
                )
                continue

            now = datetime.now(UTC)
            start_date = now.strftime(MPT_DATE_TIME_FORMAT)
            renewal_date = (now + relativedelta(months=1)).strftime(MPT_DATE_TIME_FORMAT)

            subscription = {
                "name": f"Subscription for {account_name} ({account_id})",
                "parameters": {
                    "fulfillment": [
                        {
                            "externalId": FulfillmentParametersEnum.ACCOUNT_EMAIL,
                            "value": account_email,
                        },
                        {
                            "externalId": FulfillmentParametersEnum.ACCOUNT_NAME,
                            "value": account_name,
                        },
                    ]
                },
                "externalIds": {
                    "vendor": account_id,
                },
                "startDate": start_date,
                "commitmentDate": renewal_date,
                "autoRenew": True,
                "agreement": {"id": agreement["id"]},
                "lines": [{"item": item, "quantity": 1} for item in items],
            }

            if dry_run:
                logger.info(
                    f"{agreement.get("id")} - Subscription for {account_id} "
                    f"({subscription["name"]}) to be created: {subscription}"
                )
                continue

            subscription = create_agreement_subscription(mpt_client, subscription)
            logger.info(
                f"{agreement.get("id")} - Subscription for {account_id} "
                f'({subscription["id"]}) created'
            )
            ffc_client = get_ffc_client()
            create_finops_entitlement(
                ffc_client, account_id, agreement["buyer"]["id"], agreement["id"]
            )
        except Exception as e:
            logger.error(f"{agreement.get("id")} - Failed to synchronize account {account_id}: {e}")


def sync_agreement_subscriptions(mpt_client, aws_client, agreement, dry_run=False):
    """
    Synchronize the subscriptions of a specific agreement.
    Args:
        mpt_client: The MPT client.
        aws_client: The AWS client.
        agreement: The agreement to synchronize.
        dry_run: Whether to perform a dry run.
    """
    logger.info(f"{agreement.get('id')} - Synchronizing subscriptions")
    subscription_status_to_skip = [
        SubscriptionStatusEnum.UPDATING,
        SubscriptionStatusEnum.TERMINATING,
        SubscriptionStatusEnum.CONFIGURING,
    ]
    processing_subscriptions = list(
        filter(
            lambda sub: sub["status"] in subscription_status_to_skip,
            agreement["subscriptions"],
        ),
    )

    if len(processing_subscriptions) > 0:
        logger.info(f"{agreement.get("id")} - Skipping - Has processing subscriptions")
        return
    mpa_account_id = agreement.get("externalIds", {}).get("vendor")
    active_accounts = _get_active_accounts(aws_client, agreement.get("id"), mpa_account_id)
    if not active_accounts:
        logger.info(f"{agreement.get('id')} - Skipping - No active AWS Linked accounts")
        return
    _synchronize_new_accounts(mpt_client, agreement, active_accounts, dry_run)
