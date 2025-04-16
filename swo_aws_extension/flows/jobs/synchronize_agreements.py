import logging

from mpt_extension_sdk.mpt_http.mpt import (
    create_agreement_subscription,
    get_agreements_by_ids,
    get_all_agreements,
    get_product_items_by_skus,
)
from mpt_extension_sdk.mpt_http.utils import find_first

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.constants import (
    AWS_ITEM_SKU,
    SWO_EXTENSION_MANAGEMENT_ROLE,
    TAG_AGREEMENT_ID,
    SubscriptionStatusEnum,
)
from swo_aws_extension.notifications import send_error
from swo_aws_extension.parameters import FulfillmentParametersEnum

logger = logging.getLogger(__name__)


def synchronize_agreements(mpt_client, config, agreement_ids, dry_run):
    """
    Synchronize all agreements.

    Args:
        mpt_client: The MPT client.
        config: The configuration object.
        agreement_ids: List of specific agreement IDs to synchronize.
        dry_run: Whether to perform a dry run.
    """
    if agreement_ids:
        agreements = get_agreements_by_ids(mpt_client, agreement_ids)
    else:
        agreements = get_all_agreements(mpt_client)
    for agreement in agreements:
        mpa_account = agreement.get("externalIds", {}).get("vendor", "")
        if not mpa_account:
            logger.error(f"{agreement.get('id')} - Skipping - MPA not found")
            return
        aws_client = AWSClient(config, mpa_account, SWO_EXTENSION_MANAGEMENT_ROLE)

        sync_agreement_subscriptions(mpt_client, aws_client, agreement, dry_run)


def _get_active_accounts_by_agreement_id(aws_client, agreement_id):
    """
    Get active accounts by agreement ID.
    Args:
        aws_client: The AWS client.
        agreement_id: The agreement ID.
    Returns:
        List of active accounts associated with the agreement ID.
    """

    accounts = aws_client.list_accounts()
    agreement_accounts = []
    for account in accounts:
        account_id = account["Id"]
        account_state = account["Status"]
        if account_state != "ACTIVE":
            logger.info(
                f"{agreement_id} - Skipping - Import Account {account_id} as it is not active"
            )
            continue
        tags = aws_client.get_tags_for_resource(account_id)
        agreement_tag = find_first(
            lambda tag: tag["Key"] == TAG_AGREEMENT_ID,
            tags,
        )
        if not agreement_tag:
            logger.error(
                f"{agreement_id} - Skipping - Missing Account tag for account {account_id}"
            )
            send_error(
                "Synchronize AWS agreement subscriptions - Missing Account tag",
                f"{agreement_id} - Missing Linked Account 'agreement_id'"
                f" tag for account {account_id}",
            )
            continue
        if agreement_tag["Value"] != agreement_id:
            logger.info(
                f"{agreement_id} - Skipping - Account {account_id} is part of "
                f"the agreement {agreement_tag["Value"]}"
            )
            continue
        agreement_accounts.append(account)
    return agreement_accounts


def _synchronize_new_accounts(mpt_client, agreement, agreement_accounts, dry_run):
    """
    Synchronize new AWS linked accounts for a specific agreement.
    Args:
        mpt_client: The MPT client.
        agreement: The agreement to synchronize.
        agreement_accounts: List of accounts associated with the agreement.
        dry_run: Whether to perform a dry run.

    """
    for account in agreement_accounts:
        account_id = account["Id"]
        account_email = account["Email"]
        account_name = account["Name"]
        try:
            existing_subscriptions = find_first(
                lambda sub, acc_id=account_id: sub.get("externalIds", {}).get("vendor") == acc_id
                and sub.get("status") == "Active",
                agreement["subscriptions"],
            )
            if existing_subscriptions:
                logger.info(
                    f"{agreement.get("id")} - Skipping - Create subscription for "
                    f"account={account_id} email={account_email} as it already exist"
                )
                continue
            items = get_product_items_by_skus(
                mpt_client, agreement.get("product").get("id"), [AWS_ITEM_SKU]
            )
            if not items:
                logger.error(
                    f"{agreement.get("id")} - Failed to get product items with sku {AWS_ITEM_SKU}"
                )
                continue

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
                # TODO pending to confirm dates with PDM
                "startDate": "2025-04-16T11:00:00.000Z",
                "commitmentDate": "2025-05-08T03:00:00.000Z",
                "autoRenew": True,
                "agreement": {"id": agreement["id"]},
                "lines": [{"item": items[0], "quantity": 1}],
            }

            if dry_run:
                logger.info(
                    f"{agreement.get("id")} - Subscription for {account_id} "
                    f"({subscription["id"]}) to be created: {subscription}"
                )
            else:
                subscription = create_agreement_subscription(mpt_client, subscription)
                logger.info(
                    f"{agreement.get("id")} - Subscription for {account_id} "
                    f'({subscription["id"]}) created'
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

    agreement_accounts = _get_active_accounts_by_agreement_id(aws_client, agreement.get("id"))
    if not agreement_accounts:
        logger.info(f"{agreement.get('id')} - Skipping - No active AWS Linked accounts")
        return
    _synchronize_new_accounts(mpt_client, agreement, agreement_accounts, dry_run)
