"""
Billing Journal Generator

This module provides the BillingJournalGenerator class, which is responsible for generating
and uploading billing journals for AWS Marketplace accounts, based on agreements, subscriptions,
and usage reports. It integrates with MPT API and AWS cost reports.

Entry point: BillingJournalGenerator.generate_billing_journals()
"""

import calendar
import logging
from contextlib import contextmanager
from datetime import date
from io import BytesIO
from urllib.parse import urljoin

from mpt_extension_sdk.mpt_http.mpt import _paginated, get_agreements_by_query
from mpt_extension_sdk.mpt_http.utils import find_first
from swo.mpt.extensions.runtime.tracer import dynamic_trace_span

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.constants import (
    AWS_BILLING_SUCCESS,
    AWS_MARKETPLACE,
    COST_EXPLORER_DATE_FORMAT,
    JOURNAL_PENDING_STATUS,
    SWO_EXTENSION_BILLING_ROLE,
    SYNCHRONIZATION_ERROR,
    AgreementStatusEnum,
    AWSRecordTypeEnum,
    SubscriptionStatusEnum,
    UsageMetricTypeEnum,
)
from swo_aws_extension.flows.jobs.billing_journal.error import AWSBillingException
from swo_aws_extension.flows.jobs.billing_journal.item_journal_line import create_journal_line
from swo_aws_extension.notifications import Button, send_error, send_success
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


def get_report_amount(amount):
    """
    Converts a string amount to a float, handling both comma and dot as decimal separators.
    Args:
        amount (str): The amount as a string, potentially with commas or dots.
    Returns:
        float: The amount converted to a float.
    """
    return float(amount.replace(",", ".") if "," in amount else amount)


class BillingJournalGenerator:
    def __init__(
        self,
        mpt_client,
        config,
        year,
        month,
        product_ids,
        billing_journal_processor,
        authorizations=None,
    ):
        """
        Initializes the billing journal generator with the required parameters.

        Args:
            mpt_client (MPTClient): MPT API client instance.
            config (Config): Configuration object containing AWS settings.
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
        self.journal_line_processors = billing_journal_processor
        self.journal_file_lines = []

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
        return start_date.strftime(COST_EXPLORER_DATE_FORMAT), end_date.strftime(
            COST_EXPLORER_DATE_FORMAT
        )

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
                f"Creating new journal for authorization {authorization_id}:"
                f" {journal_payload['name']}",
            )
            journal = self.mpt_api_client.billing.journal.create(journal_payload)
        else:
            self._log(
                "info", f"Found {len(journals)} journals for authorization {authorization_id}"
            )
            journal = find_first(
                lambda j: j.get("status") in JOURNAL_PENDING_STATUS,
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
        """
        mpa_account = agreement.get("externalIds", {}).get("vendor", "")
        self._log("info", f"Start generating journal lines for organization account: {mpa_account}")

        if not mpa_account:
            self._log("error", f"{agreement.get('id')} - Skipping - MPA not found")
            return
        try:
            aws_client = AWSClient(self.config, mpa_account, SWO_EXTENSION_BILLING_ROLE)
        except AWSError as ex:
            self._log(
                "exception",
                f"{agreement.get('id')} - Failed to create AWS client for MPA account"
                f" {mpa_account}: {ex}",
            )
            return
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
                    if subscription.get("status") == SubscriptionStatusEnum.TERMINATED:
                        continue
                    if not first_active_subscription:
                        first_active_subscription = subscription
                    self._generate_subscription_journal_lines(
                        subscription,
                        aws_client,
                        organization_reports,
                        journal_details,
                        organization_invoices,
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
        self._generate_mpa_journal_lines(
            mpa_account,
            first_active_subscription,
            aws_client,
            organization_reports,
            organization_invoices,
            journal_details,
        )
        self._log(
            "info",
            f"Generated journal lines for organization account: {mpa_account}",
        )

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
        self.journal_file_lines = []
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
                    self._generate_agreement_journal_lines(agreement)
            except Exception as exc:
                self._log(
                    "exception", f"{agreement.get('id')} - Failed to synchronize agreement: {exc}"
                )
                send_error(
                    SYNCHRONIZATION_ERROR,
                    f"Failed to generate billing journal for {agreement.get('id')}: {exc}",
                )

        if not self.journal_file_lines:
            self._log("info", f"No journal lines generated for authorization {authorization['id']}")
            return
        self._log(
            "info",
            f"Found {len(self.journal_file_lines)} journal lines for journal ID {journal_id}",
        )
        journal_file = "".join(entry.to_jsonl() for entry in self.journal_file_lines)
        final_file = BytesIO(journal_file.encode("utf-8"))
        self.mpt_api_client.billing.journal.upload(journal_id, final_file, "journal.jsonl")
        self._log("info", f"Uploaded journal file for journal ID {journal_id}")

        journal_link = urljoin(
            self.config.mpt_portal_base_url,
            f"/billing/journals/{journal_id}",
        )

        send_success(
            AWS_BILLING_SUCCESS,
            f"Billing journal {journal_id} updated for {authorization['id']} "
            f"with {len(self.journal_file_lines)} lines.",
            button=Button(f"Open journal {journal_id}", journal_link),
        )

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
        """
        account_id = subscription.get("externalIds", {}).get("vendor")
        self._log("info", f"Processing subscription for account {account_id}:")
        account_metrics = self._get_account_metrics(aws_client, organization_reports, account_id)
        account_invoices = organization_invoices.get(account_id, {})
        self._get_journal_lines_by_account(
            subscription, account_metrics, journal_details, account_invoices
        )
        self._log("info", f"Generated journal lines for account {account_id}")

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

    def _get_record_type_and_service_cost_by_account_report(self, aws_client, account_id):
        """
        Gets the record type and service cost report for a specific account.

        Args:
            aws_client (AWSClient): AWS client instance.
            account_id (str): AWS account ID.
        Returns:
            list: Record type and service cost report data.
        """
        group_by = [
            {"Type": "DIMENSION", "Key": "RECORD_TYPE"},
            {"Type": "DIMENSION", "Key": "SERVICE"},
        ]
        filter_by = {"Dimensions": {"Key": "LINKED_ACCOUNT", "Values": [account_id]}}
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
            invoice_entity = invoice_summary.get("Entity", {}).get("InvoicingEntity")
            invoice_account_id = invoice_summary.get("AccountId")
            invoice_id = invoice_summary.get("InvoiceId")
            if invoice_account_id not in invoices:
                invoices[invoice_account_id] = {}
            if invoice_entity in invoices[invoice_account_id]:
                invoices[invoice_account_id][invoice_entity]["invoice_id"] += invoice_id
            else:
                invoices[invoice_account_id][invoice_entity] = {
                    "invoice_id": invoice_summary.get("InvoiceId"),
                    "total_amount": invoice_summary.get("BaseCurrencyAmount", {}).get(
                        "TotalAmount"
                    ),
                    "currency_code": invoice_summary.get("BaseCurrencyAmount", {}).get(
                        "CurrencyCode"
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
        return {
            UsageMetricTypeEnum.MARKETPLACE.value: self._get_marketplace_usage_report(aws_client)
        }

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
        account_metrics[UsageMetricTypeEnum.SERVICE_INVOICE_ENTITY.value] = (
            self._get_invoice_entity_by_service(service_invoice_entity)
        )
        record_type_and_service_cost = self._get_record_type_and_service_cost_by_account_report(
            aws_client, account_id
        )
        account_metrics[UsageMetricTypeEnum.USAGE.value] = self._get_metrics_by_key(
            record_type_and_service_cost, AWSRecordTypeEnum.USAGE
        )
        account_metrics[UsageMetricTypeEnum.SUPPORT.value] = self._get_metrics_by_key(
            record_type_and_service_cost, AWSRecordTypeEnum.SUPPORT
        )
        account_metrics[UsageMetricTypeEnum.REFUND.value] = self._get_metrics_by_key(
            record_type_and_service_cost, AWSRecordTypeEnum.REFUND
        )
        account_metrics[UsageMetricTypeEnum.SAVING_PLANS.value] = self._get_metrics_by_key(
            record_type_and_service_cost, AWSRecordTypeEnum.SAVING_PLAN_RECURRING_FEE
        )
        account_metrics[UsageMetricTypeEnum.PROVIDER_DISCOUNT.value] = self._get_metrics_by_key(
            record_type_and_service_cost, AWSRecordTypeEnum.SOLUTION_PROVIDER_PROGRAM_DISCOUNT
        )
        account_metrics[UsageMetricTypeEnum.RECURRING.value] = self._get_metrics_by_key(
            record_type_and_service_cost, AWSRecordTypeEnum.RECURRING
        )
        return account_metrics

    def _get_journal_lines_by_account(
        self, subscription, account_metrics, journal_details, account_invoices
    ):
        """
        Generates all journal lines for an account and its associated subscriptions.

        Args:
            subscription (dict): Subscription object.
            account_metrics (dict): Account metrics.
            journal_details (dict): Journal metadata.
            account_invoices (dict): Invoices for the account.
        """
        account_id = subscription.get("externalIds", {}).get("vendor", "")
        for line in subscription.get("lines", []):
            item_external_id = line.get("item", {}).get("externalIds", {}).get("vendor")
            try:
                processor = self.journal_line_processors.get(item_external_id)
                if not processor:
                    self._log("error", f"No processor found for item externalId {item_external_id}")
                    continue
                self.journal_file_lines.extend(
                    processor.process(
                        account_id,
                        item_external_id,
                        account_metrics,
                        journal_details,
                        account_invoices,
                    )
                )
            except AWSBillingException as ex:
                self._log(
                    "exception",
                    f"Failed to process subscription line {line.get('id')}: {ex}",
                )
                error_line = self._manage_line_error(
                    account_id,
                    item_external_id,
                    account_metrics,
                    journal_details,
                    account_invoices,
                    ex,
                )

                self.journal_file_lines.append(error_line)

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
                amount = get_report_amount(
                    group.get("Metrics", {}).get("UnblendedCost", {}).get("Amount", "0")
                )

                if amount == 0:
                    continue
                if group["Keys"][1] not in result:
                    result[group["Keys"][1]] = {}
                result[group["Keys"][1]] = amount
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
        """
        if not first_active_subscription:
            self._log(
                "info", f"No active subscriptions found to report MPA account {mpa_account} usage"
            )
            return
        account_metrics = self._get_account_metrics(aws_client, organization_reports, mpa_account)
        account_invoices = organization_invoices.get(mpa_account, {})

        self._get_journal_lines_by_account(
            first_active_subscription,
            account_metrics,
            journal_details,
            account_invoices,
        )

    @staticmethod
    def _manage_line_error(
        account_id, item_external_id, account_metrics, journal_details, account_invoices, ex
    ):
        """
        Creates a journal line with error description for a specific account and item.
        Args:
            account_id (str): AWS account ID.
            item_external_id (str): External item ID.
            account_metrics (dict): Metrics for the account.
            journal_details (dict): Journal metadata.
            account_invoices (dict): Invoices for the account.
            ex (AWSBillingException): Error message to include in the journal line.
        """
        service_name = ex.service_name
        invoice_id = ""
        invoice_entity = ""
        if service_name:
            invoice_entity = account_metrics.get(
                UsageMetricTypeEnum.SERVICE_INVOICE_ENTITY.value, {}
            ).get(service_name, "")
            invoice_id = account_invoices.get(invoice_entity, {}).get("invoice_id", "")
        amount = ex.amount
        error_message = ex.message

        return create_journal_line(
            service_name,
            amount,
            item_external_id,
            account_id,
            journal_details,
            invoice_id,
            invoice_entity,
            error=error_message,
        )
