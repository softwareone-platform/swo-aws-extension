import calendar
import logging
from datetime import date

from mpt_extension_sdk.mpt_http.mpt import get_agreements_by_query
from mpt_extension_sdk.mpt_http.utils import find_first

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.constants import SWO_EXTENSION_BILLING_ROLE
from swo_aws_extension.notifications import send_error
from swo_mpt_api import MPTAPIClient
from swo_rql import RQLQuery

logger = logging.getLogger(__name__)


def get_billing_period(year, month):
    """
    Get the start and end dates of the billing period for a given year and month.

    Args:
        year (int): The year for the billing period.
        month (int): The month for the billing period (1-12).

    Returns:
        tuple: A tuple containing the start and end dates in "YYYY-MM-DD" format.
    """
    start_date = date(year, month, 1)

    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)

    return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")


def create_journal_line(service_name, amount, item_external_id, account_id, journal_details):
    """
    Create a new journal line dictionary for billing purposes.

    Args:
        service_name (str): The name of the service.
        amount (float): The amount for the journal line.
        item_external_id (str): The external ID of the item.
        account_id (str): The account ID.
        journal_details (dict): Details for the journal line.

    Returns:
        dict: The journal line dictionary.
    """
    return {
        "description": {
            "value1": service_name,
            "value2": f"{account_id}/{journal_details["invoice_name"]}",
        },
        "externalIds": {
            "invoice": journal_details["invoice_id"],
            "reference": journal_details["agreement_id"],
            "vendor": journal_details["mpa_id"],
        },
        "period": {"start": journal_details["start_date"], "end": journal_details["end_date"]},
        "price": {"PPx1": amount, "unitPP": amount},
        "quantity": 1,
        "search": {
            "item": {
                "criteria": "item.externalIds.vendor",
                "value": item_external_id,
            },
            "subscription": {
                "criteria": "subscription.externalIds.vendor",
                "value": account_id,
            },
        },
    }


def get_journal_lines_by_item(
    account_id,
    item_external_id,
    metrics,
    journal_details,
):
    """
    Generate journal lines for a given item based on its metrics.

    Args:
        account_id (str): The account ID.
        item_external_id (str): The external ID of the item.
        metrics (dict): The metrics for the item.
        journal_details (dict): Details for the journal line.

    Returns:
        list: List of journal lines.
    """
    journal_lines = []

    if item_external_id == "AWS Marketplace":
        for sub_key, amount in metrics.get("MARKETPLACE_USAGE", {}).items():
            service_name = sub_key.split(",")[1] if "," in sub_key else sub_key
            if service_name != "Tax":
                logger.info(f"        - {service_name}: {amount}")
                journal_lines.append(
                    create_journal_line(
                        service_name, amount, item_external_id, account_id, journal_details
                    )
                )
        return journal_lines

    logger.info(f"ERROR: Failed to get usage lines for item external_id: {item_external_id}")
    return []


def get_metrics_by_key(report, key):
    """
    Extract metrics for a specific key from the AWS cost report.

    Args:
        report (dict): The AWS cost report.
        key (str): The key to extract metrics for.

    Returns:
        dict: The extracted metrics for the key.
    """
    try:
        result = {}
        groups = report["ResultsByTime"][0]["Groups"]
        for group in groups:
            if key in group["Keys"]:
                if group["Keys"][1] not in result:
                    result[group["Keys"][1]] = {}
                amount = group.get("Metrics", {}).get("UnblendedCost", {}).get("Amount", "0")
                amount = amount.replace(",", ".") if "," in amount else amount
                result[group["Keys"][1]] = float(amount)
        return result
    except (KeyError, IndexError, ValueError) as e:
        logger.error(f"Error processing key '{key}': {e}")
        raise


def get_authorizations(mpt_client, rql_query):
    """
    Retrieve authorizations based on the provided RQL query.

    Args:
        mpt_client: The MPT client instance.
        rql_query: The RQL query to filter authorizations.

    Returns:
        dict or None: A dictionary containing the authorization data, or None if the request fails.
    """
    url = (
        f"/catalog/authorizations?{rql_query}&select=externalIds,product"
        if rql_query
        else "/catalog/authorizations?select=externalIds,product"
    )
    response = mpt_client.get(url)

    if response.status_code == 200:
        return response.json()["data"] if "data" in response.json() else None
    logger.error(f"Failed to retrieve authorizations: {response.status_code} - {response.text}")
    return None


def obtain_journal_id(mpt_api_client, authorization_id, external_id, year, month, month_name):
    """
    Get or create a billing journal ID for a given authorization and external ID.

    Args:
        mpt_api_client: The MPT API client instance.
        authorization_id (str): The ID of the authorization.
        external_id (str): The external ID for the journal.
        year (int): The billing year.
        month (int): The billing month (1-12).
        month_name (str): The name of the month (e.g., "January").

    Returns:
        str: The journal ID.
    """
    rql_query = RQLQuery(externalIds__vendor=external_id) & RQLQuery(
        authorization__id=authorization_id
    )
    print("RQL Query:", rql_query)
    journals = mpt_api_client.billing.journal.query(rql_query).all()
    print(f"Found {len(journals)} journals")
    if len(journals) == 0:
        journal_payload = {
            "name": f"1 {month_name} {year} #1",
            "authorization": {"id": authorization_id},
            "dueDate": f"{year}-{month}-01",
            "externalIds": {"vendor": external_id},
        }
        logger.info(f"Creating new journal for authorization {authorization_id}: {journal_payload}")
        # journal = mpt_api_client.billing.journal.create(journal_payload)
    else:
        logger.info(f"Found {len(journals)} journals for authorization {authorization_id}")
        journal = find_first(
            lambda j: j.get("status") in ["Error", "Draft", "Validated"],
            journals,
            None,
        )
        if not journal:
            journal_payload = {
                "name": f"1 {month_name} {year} #{len(journals)}",
                "authorization": {"id": authorization_id},
                "dueDate": f"{year}-{month}-01",
                "externalIds": {"vendor": external_id},
            }
            logger.info(
                f"Creating new journal for authorization {authorization_id}: {journal_payload}"
            )
            # journal = mpt_api_client.billing.journal.create(journal_payload)

    return journal.get("id")


def get_authorization_agreements(mpt_client, authorization, product_ids):
    """
    Retrieve agreements for a given authorization filtered by product IDs.

    Args:
        mpt_client: The MPT client instance.
        authorization (dict): The authorization data containing the ID.
        product_ids (list): List of product IDs to filter agreements.

    Returns:
        list: A list of agreements that match the authorization and product IDs.
    """
    select = "&select=subscriptions,subscriptions.lines"
    rql_filter = (
        RQLQuery(authorization__id=authorization.get("id"))
        & RQLQuery(status__in=["Active", "Updating"])
        & RQLQuery(product__id__in=product_ids)
    )
    print("RQL Filter:", rql_filter)
    rql_query = f"{rql_filter}{select}"
    print(rql_query)
    agreements = get_agreements_by_query(mpt_client, rql_query)
    return agreements


def generate_agreement_journal_lines(agreement, config, start_date, end_date):
    """
    Generate journal lines for a given agreement based on its subscriptions and items.

    Args:
        agreement (dict): The agreement data containing subscriptions and items.
        config (dict): The configuration object containing AWS credentials.
        start_date (str): The start date of the billing period in "YYYY-MM-DD" format.
        end_date (str): The end date of the billing period in "YYYY-MM-DD" format.

    Returns:
        list: A list of journal lines generated for the agreement.
    """
    agreement_journal_lines = []
    try:
        mpa_account = agreement.get("externalIds", {}).get("vendor", "")
        if not mpa_account:
            logger.error(f"{agreement.get('id')} - Skipping - MPA not found")
            return agreement_journal_lines
        aws_client = AWSClient(config, mpa_account, SWO_EXTENSION_BILLING_ROLE)

        journal_details = {
            "invoice_name": "",
            "invoice_id": "",
            "agreement_id": agreement.get("id"),
            "mpa_id": mpa_account,
            "start_date": start_date,
            "end_date": end_date,
        }
        invoice_summaries = aws_client.list_invoice_summaries_by_account_id(
            mpa_account, start_date, end_date
        )
        # how to map by service
        logger.info(f"Found {len(invoice_summaries)} invoice summaries")
        marketplace_usage_report = get_marketplace_usage_report(aws_client, end_date, start_date)

        for subscription in agreement.get("subscriptions", []):
            if subscription.get("status") != "Active":
                continue

            subscription_id = subscription.get("id")
            account_id = subscription.get("externalIds", {}).get("vendor")
            logger.info(f"Processing subscription {subscription_id} for account {account_id}:")
            marketplace_metrics = get_metrics_by_key(marketplace_usage_report, account_id)
            for line in subscription.get("lines", []):
                item_external_id = line.get("item", {}).get("externalIds", {}).get("vendor")
                logger.info(f"Processing item {item_external_id}:")
                agreement_journal_lines.extend(
                    get_journal_lines_by_item(
                        account_id, item_external_id, marketplace_metrics, journal_details
                    )
                )
        return agreement_journal_lines

    except Exception as e:
        logger.exception(f"{agreement.get('id')} - Failed to synchronize agreement: {e}")
        send_error(
            "AWS Billing Journal Synchronization Error",
            f"Failed to generate billing journal for {agreement.get('id')}: {e}",
        )
        return agreement_journal_lines


def get_marketplace_usage_report(aws_client, end_date, start_date):
    """
    Retrieve the AWS Marketplace usage report for the specified date range.
    Args:
        aws_client (AWSClient): The AWS client instance.
        end_date (str): The end date of the report in "YYYY-MM-DD" format.
        start_date (str): The start date of the report in "YYYY-MM-DD" format.

    Returns:
        dict: The AWS Marketplace usage report containing cost and usage data.

    """
    group_by = [
        {"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"},
        {"Type": "DIMENSION", "Key": "SERVICE"},
    ]
    filter_by = {"Dimensions": {"Key": "BILLING_ENTITY", "Values": ["AWS Marketplace"]}}
    return aws_client.get_cost_and_usage(start_date, end_date, group_by, filter_by)


def generate_billing_journals(mpt_client, config, year, month, product_ids, authorizations=None):
    """
    Generate billing journals for the given month and year, filtered by product IDs and optional authorizations.

    Args:
        mpt_client: The MPT client instance.
        config Config: The configuration object.
        year (int): The billing year.
        month (int): The billing month (int).
        product_ids (list): List of product IDs to filter agreements.
        authorizations (list, optional): Optional list of authorization IDs to filter.
    """
    start_date, end_date = get_billing_period(year, month)
    logger.info(f"Generating billing journals for {start_date} / {end_date}")
    rql_query = RQLQuery(product__id__in=product_ids)
    if authorizations:
        authorizations = list(set(authorizations))
        rql_query = RQLQuery(id__in=authorizations) & rql_query

    list_authorizations = get_authorizations(mpt_client, rql_query)

    if list_authorizations is None:
        return

    month_name = calendar.month_name[month]

    for authorization in list_authorizations:
        mpt_api_client = MPTAPIClient(mpt_client)
        external_id = f"AWS-{year}-{month_name}"
        journal_file_lines = []

        journal_id = obtain_journal_id(
            mpt_api_client, authorization["id"], external_id, year, month, month_name
        )
        logger.info(f"Generating journal lines for journal ID: {journal_id}")

        agreements = get_authorization_agreements(mpt_client, authorization, product_ids)
        if not agreements:
            logger.info(f"No agreements found for authorization {authorization['id']}")
            continue
        logger.info(f"Found {len(agreements)} agreements for authorization {authorization['id']}")
        for agreement in agreements:
            journal_file_lines.extend(
                generate_agreement_journal_lines(agreement, config, start_date, end_date)
            )
            return
        print("###########")
        print(journal_file_lines)
