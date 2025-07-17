"""
Billing Journal Generator

This module provides the BillingJournalGenerator class, which is responsible for generating
and uploading billing journals for AWS Marketplace accounts, based on agreements, subscriptions,
and usage reports. It integrates with MPT API and AWS cost reports.

Entry point: BillingJournalGenerator.generate_billing_journals()
"""

import calendar
import json
import logging
from contextlib import contextmanager
from datetime import date
from io import BytesIO

from mpt_extension_sdk.mpt_http.mpt import _paginated, get_agreements_by_query
from mpt_extension_sdk.mpt_http.utils import find_first
from swo.mpt.extensions.runtime.tracer import dynamic_trace_span

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.constants import (
    AMOUNT,
    AWS_MARKETPLACE,
    BASE_CURRENCY_AMOUNT,
    CURRENCY_CODE,
    CURRENCY_CODE_KEY,
    DATE_FORMAT,
    EXTERNAL_IDS,
    INVOICE_ENTITY,
    INVOICE_ID,
    INVOICE_ID_KEY,
    INVOICING_ENTITY,
    JOURNAL_PENDING_STATUS,
    MARKETPLACE,
    SERVICE_INVOICE_ENTITY,
    STATUS,
    SWO_EXTENSION_BILLING_ROLE,
    SYNCHRONIZATION_ERROR,
    TAX,
    TOTAL_AMOUNT,
    TOTAL_AMOUNT_KEY,
    UNBLENDED_COST,
    VENDOR,
    AgreementStatusEnum,
    SubscriptionStatusEnum,
)
from swo_aws_extension.notifications import send_error
from swo_mpt_api import MPTAPIClient
from swo_rql import RQLQuery

logger = logging.getLogger(__name__)


# TODO: SDK candidate
def get_authorizations(mpt_client, rql_query, limit=10):  # pragma: no cover
    """
    Retrieve authorizations based on the provided RQL query.

        Args:
            mpt_client (MPTClient): MPT API client instance.
            rql_query (RQLQuery): Query to filter authorizations.
            limit (int): Maximum number of authorizations to retrieve.
        Returns:
            list or None: List of authorizations or None if request fails.
    """
    url = (
        f"/catalog/authorizations?{rql_query}&select=externalIds,product"
        if rql_query
        else "/catalog/authorizations?select=externalIds,product"
    )
    return _paginated(mpt_client, url, limit=limit)


class BillingJournalGenerator:
    def __init__(self, mpt_client, config, year, month, product_ids, authorizations=None):
        """
        Initializes the billing journal generator with the required parameters.

        Args:
            mpt_client (MPTClient): MPT API client instance.
            config (dict): Configuration dictionary.
            year (int): Billing year.
            month (int): Billing month.
            product_ids (list): List of product IDs to process.
            authorizations (list, optional): List of authorization IDs to filter.
        """
        self.mpt_client = mpt_client
        self.config = config
        self.year = year
        self.month = month
        self.product_ids = product_ids
        self.authorizations = authorizations
        self.start_date, self.end_date = self._get_billing_period(year, month)
        self.mpt_api_client = MPTAPIClient(mpt_client)
        self.logger_context = {}

    def _log(self, level, msg):
        log_func = getattr(logger, level, logger.info)
        context_str = " ".join(str(v) for v in self.logger_context.values())
        log_func(f"{context_str} - {msg}")

    @staticmethod
    def _get_billing_period(year, month):
        """
        Returns the billing period (start and end) as date strings for a given year and month.

        Args:
        year (int): The year for the billing period.
        month (int): The month for the billing period (1-12).

        Returns:
        tuple: A tuple containing the start and end dates in "YYYY-MM-DD" format.
        """
        start_date = date(year, month, 1)
        end_date = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        return start_date.strftime(DATE_FORMAT), end_date.strftime(DATE_FORMAT)

    def _obtain_journal_id(self, authorization_id):
        """
        Gets or creates the journal ID associated with an authorization and period.

        Args:
            authorization_id (str): Authorization ID.
        Returns:
            str: Journal ID.
        """
        month_name = calendar.month_name[self.month]
        external_id = f"AWS-{self.year}-{month_name}"
        rql_query = RQLQuery(externalIds__vendor=external_id) & RQLQuery(
            authorization__id=authorization_id
        )
        journals = self.mpt_api_client.billing.journal.query(rql_query).all()
        if not journals:
            journal_payload = {
                "name": f"1 {month_name} {self.year} #1",
                "authorization": {"id": authorization_id},
                "dueDate": f"{self.year}-{self.month}-01",
                "externalIds": {"vendor": external_id},
            }
            self._log(
                "info",
                f"Creating new journal for authorization {authorization_id}: {journal_payload}",
            )
            journal = self.mpt_api_client.billing.journal.create(journal_payload)
        else:
            self._log(
                "info", f"Found {len(journals)} journals for authorization {authorization_id}"
            )
            journal = find_first(
                lambda j: j.get(STATUS) in JOURNAL_PENDING_STATUS,
                journals,
                None,
            )
            if not journal:
                journal_payload = {
                    "name": f"1 {month_name} {self.year} #{len(journals)}",
                    "authorization": {"id": authorization_id},
                    "dueDate": f"{self.year}-{self.month}-01",
                    "externalIds": {"vendor": external_id},
                }
                self._log(
                    "info",
                    f"Not found journals in {JOURNAL_PENDING_STATUS} status. Creating new journal "
                    f"for authorization {authorization_id}: {journal_payload}",
                )
                journal = self.mpt_api_client.billing.journal.create(journal_payload)
        return journal.get("id")

    def _get_authorization_agreements(self, authorization):
        """
        Retrieves agreements associated with an authorization.

        Args:
            authorization (dict): Authorization object.
        Returns:
            list: List of agreements.
        """
        select = "&select=subscriptions,subscriptions.lines"
        rql_filter = (
            RQLQuery(authorization__id=authorization.get("id"))
            & RQLQuery(status__in=[AgreementStatusEnum.ACTIVE, AgreementStatusEnum.UPDATING])
            & RQLQuery(product__id__in=self.product_ids)
        )
        rql_query = f"{rql_filter}{select}"
        return get_agreements_by_query(self.mpt_client, rql_query)

    @contextmanager
    def _temp_context(self, key, value):
        self.logger_context[key] = value
        try:
            yield
        finally:
            self.logger_context.pop(key, None)

    @dynamic_trace_span(lambda *args: f"Agreement {args[1]['id']}")
    def _generate_agreement_journal_lines(self, agreement):
        """
        Generates journal lines for an agreement, including all its active subscriptions.

        Args:
            agreement (dict): Agreement object.
        Returns:
            list: List of journal line dictionaries.
        """
        agreement_journal_lines = []
        mpa_account = agreement.get(EXTERNAL_IDS, {}).get(VENDOR, "")
        self._log("info", f"Start generating journal lines for organization account: {mpa_account}")

        if not mpa_account:
            self._log("error", f"{agreement.get('id')} - Skipping - MPA not found")
            return agreement_journal_lines
        try:
            aws_client = AWSClient(self.config, mpa_account, SWO_EXTENSION_BILLING_ROLE)
        except AWSError as ex:
            self._log(
                "exception",
                f"{agreement.get('id')} - Failed to create AWS client for MPA account"
                f" {mpa_account}: {ex}",
            )
            return agreement_journal_lines
        organization_invoices = self._get_organization_invoices(aws_client, mpa_account)
        self._log(
            "info",
            f"Found {len(organization_invoices)} organization invoice summaries:"
            f" {organization_invoices}",
        )
        journal_details = {
            "agreement_id": agreement.get("id"),
            "mpa_id": mpa_account,
            "start_date": self.start_date,
            "end_date": self.end_date,
        }
        organization_reports = self._get_organization_reports(aws_client)
        first_active_subscription = None
        for subscription in agreement.get("subscriptions", []):
            try:
                with self._temp_context("subscription_id", subscription.get("id")):
                    if subscription.get(STATUS) == SubscriptionStatusEnum.TERMINATED:
                        continue
                    if not first_active_subscription:
                        first_active_subscription = subscription
                    agreement_journal_lines.extend(
                        self._generate_subscription_journal_lines(
                            subscription,
                            aws_client,
                            organization_reports,
                            journal_details,
                            organization_invoices,
                        )
                    )
            except Exception as exc:
                self._log(
                    "exception",
                    f"Failed to process subscription {subscription.get('id')}: {exc}",
                )
                send_error(
                    SYNCHRONIZATION_ERROR,
                    f"Failed to process subscription {subscription.get('id')}: {exc}",
                )

        self._log("info", f"Generating usage lines for MPA account: {mpa_account}")
        agreement_journal_lines.extend(
            self._generate_mpa_journal_lines(
                mpa_account,
                first_active_subscription,
                aws_client,
                organization_reports,
                organization_invoices,
                journal_details,
            )
        )
        self._log(
            "info",
            f"Generated {len(agreement_journal_lines)} journal lines for organization "
            f"account: {mpa_account}",
        )

        return agreement_journal_lines

    @dynamic_trace_span(lambda *args: f"Authorization {args[1]['id']}")
    def _generate_authorization_journal(self, authorization):
        """
        Generates and uploads the billing journal for a specific authorization.

        Args:
            authorization (dict): Authorization object.
        Returns:
            None
        """
        self._log("info", f"Generating billing journals for {authorization['id']}")
        journal_file_lines = []
        journal_id = self._obtain_journal_id(authorization["id"])
        self._log("info", f"Generating journal lines for journal ID: {journal_id}")
        agreements = self._get_authorization_agreements(authorization)
        if not agreements:
            self._log("info", f"No agreements found for authorization {authorization['id']}")
            return
        self._log(
            "info", f"Found {len(agreements)} agreements for authorization {authorization['id']}"
        )

        for agreement in agreements:
            try:
                with self._temp_context("agreement_id", agreement.get("id")):
                    journal_file_lines.extend(self._generate_agreement_journal_lines(agreement))
            except Exception as exc:
                self._log(
                    "exception", f"{agreement.get('id')} - Failed to synchronize agreement: {exc}"
                )
                send_error(
                    SYNCHRONIZATION_ERROR,
                    f"Failed to generate billing journal for {agreement.get('id')}: {exc}",
                )

        if not journal_file_lines:
            self._log("info", f"No journal lines generated for authorization {authorization['id']}")
            return
        self._log(
            "info", f"Found {len(journal_file_lines)} journal lines for journal ID {journal_id}"
        )
        journal_file = "".join(json.dumps(entry) + "\n" for entry in journal_file_lines)
        final_file = BytesIO(journal_file.encode("utf-8"))
        self.mpt_api_client.billing.journal.upload(journal_id, final_file, "journal.jsonl")
        self._log("info", f"Uploaded journal file for journal ID {journal_id}")

    def generate_billing_journals(self):
        """
        Entry point for generating billing journals for all selected authorizations.

        Returns:
            None
        """
        self._log("info", f"Generating billing journals for {self.start_date} / {self.end_date}")
        rql_query = RQLQuery(product__id__in=self.product_ids)
        if self.authorizations:
            authorizations = list(set(self.authorizations))
            rql_query = RQLQuery(id__in=authorizations) & rql_query

        list_authorizations = get_authorizations(self.mpt_client, rql_query)
        if list_authorizations is None:
            return
        for authorization in list_authorizations:
            try:
                with self._temp_context("authorization_id", authorization.get("id")):
                    self._generate_authorization_journal(authorization)
            except Exception as exc:
                self._log(
                    "exception",
                    f"Failed to generate billing journals for authorization"
                    f" {authorization.get('id')}: {exc}",
                )
                send_error(
                    SYNCHRONIZATION_ERROR,
                    "Failed to generate billing journals for authorization",
                )

    @dynamic_trace_span(lambda *args: f"Subscription {args[1]['id']}")
    def _generate_subscription_journal_lines(
        self,
        subscription,
        aws_client,
        organization_reports,
        journal_details,
        organization_invoices,
    ):
        """
        Generates journal lines for a specific subscription.

        Args:
            subscription (dict): Subscription object.
            aws_client (AWSClient): AWS client instance.
            organization_reports (dict): Organization usage reports.
            journal_details (dict): Journal metadata.
            organization_invoices (dict): Invoices for the organization.
        Returns:
            list: List of journal line dictionaries.
        """
        subscription_journal_lines = []
        account_id = subscription.get(EXTERNAL_IDS, {}).get(VENDOR)
        self._log("info", f"Processing subscription for account {account_id}:")
        account_metrics = self._get_account_metrics(aws_client, organization_reports, account_id)
        account_invoices = organization_invoices.get(account_id, {})
        subscription_journal_lines.extend(
            self._get_journal_lines_by_account(
                account_id, subscription, account_metrics, journal_details, account_invoices
            )
        )
        self._log(
            "info",
            f"Generated {len(subscription_journal_lines)} journal lines for account {account_id}",
        )
        return subscription_journal_lines

    def _get_marketplace_usage_report(self, aws_client):
        """
        Gets the AWS Marketplace usage report for the given period and client.

        Args:
            aws_client (AWSClient): AWS client instance.
        Returns:
            list: Usage report data.
        """
        group_by = [
            {"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"},
            {"Type": "DIMENSION", "Key": "SERVICE"},
        ]
        filter_by = {"Dimensions": {"Key": "BILLING_ENTITY", "Values": [AWS_MARKETPLACE]}}
        return aws_client.get_cost_and_usage(self.start_date, self.end_date, group_by, filter_by)

    def _get_service_invoice_entity_by_account_id_report(self, aws_client, account_id):
        """
        Gets the invoice entity by service report for a specific account.

        Args:
            aws_client (AWSClient): AWS client instance.
            account_id (str): AWS account ID.
        Returns:
            list: Service invoice entity report data.
        """
        group_by = [
            {"Type": "DIMENSION", "Key": "SERVICE"},
            {"Type": "DIMENSION", "Key": "INVOICING_ENTITY"},
        ]
        filter_by = {"Dimensions": {"Key": "LINKED_ACCOUNT", "Values": [account_id]}}
        return aws_client.get_cost_and_usage(self.start_date, self.end_date, group_by, filter_by)

    def _get_organization_invoices(self, aws_client, mpa_account):
        """
        Gets the organization invoice summaries for a given account and period.

        Args:
            aws_client (AWSClient): AWS client instance.
            mpa_account (str): AWS account ID.

        Returns:
        dict: A dictionary containing invoice summaries grouped by account ID and entity.
        """
        invoice_summaries = aws_client.list_invoice_summaries_by_account_id(
            mpa_account, self.start_date, self.end_date
        )
        invoices = {}
        for invoice_summary in invoice_summaries:
            invoice_entity = invoice_summary.get(INVOICE_ENTITY, {}).get(INVOICING_ENTITY)
            invoice_account_id = invoice_summary.get("AccountId")
            invoice_id = invoice_summary.get(INVOICE_ID_KEY)
            if invoice_account_id not in invoices:
                invoices[invoice_account_id] = {}
            if invoice_entity in invoices[invoice_account_id]:
                invoices[invoice_account_id][invoice_entity][INVOICE_ID] += invoice_id
            else:
                invoices[invoice_account_id][invoice_entity] = {
                    INVOICE_ID: invoice_summary.get(INVOICE_ID_KEY),
                    TOTAL_AMOUNT: invoice_summary.get(BASE_CURRENCY_AMOUNT, {}).get(
                        TOTAL_AMOUNT_KEY
                    ),
                    CURRENCY_CODE: invoice_summary.get(BASE_CURRENCY_AMOUNT, {}).get(
                        CURRENCY_CODE_KEY
                    ),
                }
        return invoices

    def _get_organization_reports(self, aws_client):
        """
        Returns the organization usage reports for the given period.

        Args:
        aws_client (AWSClient): The AWS client instance.

        Returns:
            dict: Organization usage reports.
        """
        return {MARKETPLACE: self._get_marketplace_usage_report(aws_client)}

    def _get_account_metrics(self, aws_client, organization_reports, account_id):
        """
        Calculates and returns account metrics for a given period and account.

        Args:
        aws_client (AWSClient): The AWS client instance.
        organization_reports (dict): The organization reports.
        account_id (str): The AWS account ID.

        Returns:
            dict: Account metrics.
        """
        account_metrics = {
            name: self._get_metrics_by_key(report, account_id)
            for name, report in organization_reports.items()
        }
        service_invoice_entity = self._get_service_invoice_entity_by_account_id_report(
            aws_client, account_id
        )
        account_metrics[SERVICE_INVOICE_ENTITY] = self._get_invoice_entity_by_service(
            service_invoice_entity
        )
        return account_metrics

    def _get_journal_lines_by_account(
        self, account_id, subscription, account_metrics, journal_details, account_invoices
    ):
        """
        Generates all journal lines for an account and its associated subscriptions.

        Args:
            account_id (str): AWS account ID.
            subscription (dict): Subscription object.
            account_metrics (dict): Account metrics.
            journal_details (dict): Journal metadata.
            account_invoices (dict): Invoices for the account.
        Returns:
            list: List of journal line dictionaries.
        """
        lines = []
        for line in subscription.get("lines", []):
            item_external_id = line.get("item", {}).get(EXTERNAL_IDS, {}).get(VENDOR)
            lines.extend(
                self._get_journal_lines_by_item(
                    account_id,
                    item_external_id=item_external_id,
                    account_metrics=account_metrics,
                    journal_details=journal_details,
                    account_invoices=account_invoices,
                )
            )
        return lines

    def _get_journal_lines_by_item(
        self, account_id, item_external_id, account_metrics, journal_details, account_invoices
    ):
        """
        Generates journal lines for a specific item of an account using associated metrics
        and invoices.

        Args:
            account_id (str): AWS account ID.
            item_external_id (str): External item ID.
            account_metrics (dict): Metrics for the account.
            journal_details (dict): Journal metadata.
            account_invoices (dict): Invoices for the account.
        Returns:
            list: List of journal line dictionaries.
        """
        journal_lines = []

        if item_external_id == AWS_MARKETPLACE:
            for sub_key, amount in account_metrics[MARKETPLACE].items():
                service_name = sub_key.split(",")[1] if "," in sub_key else sub_key
                if service_name == TAX:
                    continue
                invoice_entity = account_metrics[SERVICE_INVOICE_ENTITY].get(service_name, "")
                invoice_id = account_invoices.get(invoice_entity, {}).get(INVOICE_ID, "")
                journal_lines.append(
                    self._create_journal_line(
                        service_name,
                        amount,
                        item_external_id,
                        account_id,
                        journal_details,
                        invoice_id,
                        invoice_entity,
                    )
                )
        return journal_lines

    @staticmethod
    def _create_journal_line(
        service_name,
        amount,
        item_external_id,
        account_id,
        journal_details,
        invoice_id,
        invoice_entity,
    ):
        """
        Create a new journal line dictionary for billing purposes.

            Args:
                service_name (str): Name of the AWS service.
                amount (float): Amount to bill.
                item_external_id (str): External item ID.
                account_id (str): AWS account ID.
                journal_details (dict): Journal metadata.
                invoice_id (str): Invoice ID.
                invoice_entity (str): Invoice entity.
            Returns:
                dict: Journal line dictionary.
        """
        return {
            "description": {
                "value1": service_name,
                "value2": f"{account_id}/{invoice_entity}",
            },
            "externalIds": {
                "invoice": invoice_id,
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
            "segment": "COM",
        }

    @staticmethod
    def _get_invoice_entity_by_service(service_invoice_entity_report):
        """
        Gets the invoice entity by service from the provided report.

        Args:
            service_invoice_entity_report (list): Report data.
        Returns:
            dict: Mapping from service to invoice entity.
        """
        result = {}
        for result_by_time in service_invoice_entity_report:
            for group in result_by_time["Groups"]:
                result[group["Keys"][0]] = group["Keys"][1]
        return result

    @staticmethod
    def _get_metrics_by_key(report, key):
        """
        Extracts and returns metrics from the report for a given key.

        Args:
            report (list): AWS report data.
            key (str): Key to extract metrics for.
        Returns:
            dict: Metrics by key.
        """
        result = {}
        for result_by_time in report:
            groups = result_by_time.get("Groups", [])
            for group in groups:
                if key not in group.get("Keys", []):
                    continue
                if group["Keys"][1] not in result:
                    result[group["Keys"][1]] = {}
                amount = group.get("Metrics", {}).get(UNBLENDED_COST, {}).get(AMOUNT, "0")
                amount = amount.replace(",", ".") if "," in amount else amount
                result[group["Keys"][1]] = float(amount)
        return result

    def _generate_mpa_journal_lines(
        self,
        mpa_account,
        first_active_subscription,
        aws_client,
        organization_reports,
        organization_invoices,
        journal_details,
    ):
        """
        Generates journal lines for the MPA account, including metrics and invoices.
        Args:
            mpa_account (str): MPA account ID.
            first_active_subscription (dict): First active subscription for the MPA account.
            aws_client (AWSClient): AWS client instance.
            organization_reports (dict): Organization usage reports.
            organization_invoices (dict): Invoices for the organization.
            journal_details (dict): Journal metadata.
        Returns:
            list: List of journal line dictionaries for the MPA account.
        """
        if not first_active_subscription:
            self._log(
                "info", f"No active subscriptions found to report MPA account {mpa_account} usage"
            )
            return []
        account_metrics = self._get_account_metrics(aws_client, organization_reports, mpa_account)
        account_invoices = organization_invoices.get(mpa_account, {})
        return self._get_journal_lines_by_account(
            mpa_account,
            first_active_subscription,
            account_metrics,
            journal_details,
            account_invoices,
        )
