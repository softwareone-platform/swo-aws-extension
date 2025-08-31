"""
Billing Journal Generator.

This module provides the BillingJournalGenerator class, which is responsible for generating
and uploading billing journals for AWS Marketplace accounts, based on agreements, subscriptions,
and usage reports. It integrates with MPT API and AWS cost reports.

Entry point: BillingJournalGenerator.generate_billing_journals()
"""

import calendar
import datetime as dt
import json
import logging
from contextlib import contextmanager
from io import BytesIO
from urllib.parse import urljoin

from mpt_extension_sdk.mpt_http.mpt import _paginated, get_agreements_by_query  # noqa: PLC2701
from mpt_extension_sdk.mpt_http.utils import find_first
from mpt_extension_sdk.runtime.tracer import dynamic_trace_span

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
    AWSServiceEnum,
    JournalAttachmentFilesNameEnum,
    SubscriptionStatusEnum,
    TransferTypesEnum,
    UsageMetricTypeEnum,
)
from swo_aws_extension.file_builder.zip_builder import InMemoryZipBuilder
from swo_aws_extension.flows.jobs.billing_journal.error import AWSBillingError
from swo_aws_extension.flows.jobs.billing_journal.item_journal_line import create_journal_line
from swo_aws_extension.notifications import Button, send_error, send_success
from swo_aws_extension.parameters import get_transfer_type
from swo_mpt_api import MPTAPIClient
from swo_mpt_api.models.hints import JournalAttachment
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
    """Generate billing journal."""
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
            billing_journal_processor: billing journal processor
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
        self.organization_reports = {}
        self.authorization_currency = None

    def _log(self, level, msg):
        log_func = getattr(logger, level, logger.info)
        context_str = " ".join(str(v) for v in self.logger_context.values())
        log_func(f"{context_str} - {msg}")

    @staticmethod
    def _get_billing_period(year, month):
        start_date = dt.date(year, month, 1)
        end_date = dt.date(year + 1, 1, 1) if month == 12 else dt.date(year, month + 1, 1)
        return start_date.strftime(COST_EXPLORER_DATE_FORMAT), end_date.strftime(
            COST_EXPLORER_DATE_FORMAT
        )

    def _obtain_journal_id(self, authorization_id):
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
        select = "&select=subscriptions,subscriptions.lines,parameters"
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
    def _generate_agreement_journal_lines(self, agreement, journal_id):  # noqa: C901
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
            send_error(
                SYNCHRONIZATION_ERROR,
                f"{agreement.get('id')} - Failed to create AWS client for MPA account "
                f"{mpa_account}: {ex}",
            )
            return

        journal_details = {
            "agreement_id": agreement.get("id"),
            "mpa_id": mpa_account,
            "start_date": self.start_date,
            "end_date": self.end_date,
        }
        self.organization_reports = {
            UsageMetricTypeEnum.MARKETPLACE.value: self._get_marketplace_usage_report(aws_client),
            "invoices": self._get_invoices(aws_client, mpa_account),
            "accounts": {},
        }

        organization_invoices = self._get_organization_invoices(
            self.organization_reports["invoices"]
        )
        if not self._validate_invoice_currencies(
            agreement.get("id"),
            organization_invoices,
            self.authorization_currency,
        ):
            return

        first_active_subscription = None
        for subscription in agreement.get("subscriptions", []):
            try:
                with self._temp_context("subscription_id", subscription.get("id")):
                    if subscription.get("status") == SubscriptionStatusEnum.TERMINATED:
                        continue
                    if not subscription.get("externalIds", {}).get("vendor"):
                        self._log(
                            "error", f"Subscription {subscription.get('id')} - Account ID not found"
                        )
                        continue
                    if not first_active_subscription:
                        first_active_subscription = subscription
                    self._generate_subscription_journal_lines(
                        subscription, aws_client, journal_details, organization_invoices
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
        transfer_type = get_transfer_type(agreement)
        self._generate_mpa_journal_lines(
            mpa_account,
            first_active_subscription,
            aws_client,
            journal_details,
            transfer_type,
            organization_invoices,
        )
        total_amount = self._calculate_amount_by_account_id(mpa_account)
        self._log(
            "info",
            f"Generated journal lines for organization account {mpa_account}: {total_amount}",
        )
        self._add_attachments(agreement.get("id"), journal_id, mpa_account)

    def _add_attachments(self, agreement_id, journal_id, mpa_account):
        mimetype = "application/zip"
        filename = f"{agreement_id}-reports-{self.year}-{self.month}.zip"
        attachment = JournalAttachment(
            name=filename, description=f"Usage reports for AWS organization {mpa_account}"
        )

        self.mpt_api_client.billing.journal.attachments(journal_id).upload(
            filename=filename, mimetype=mimetype, file=self._generate_zip(), attachment=attachment
        )
        self._log("info", f"Uploaded journal attachment for MPA account {mpa_account}")

    @dynamic_trace_span(lambda *args: f"Authorization {args[1]['id']}")
    def _generate_authorization_journal(self, authorization):
        self._log("info", f"Generating billing journals for {authorization['id']}")
        self.journal_file_lines = []
        self.authorization_currency = authorization.get("currency")
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
                    self._generate_agreement_journal_lines(agreement, journal_id)
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

        journal_file = "".join(entry.to_jsonl() for entry in self.journal_file_lines)
        final_file = BytesIO(journal_file.encode("utf-8"))
        self.mpt_api_client.billing.journal.upload(journal_id, final_file, "journal.jsonl")
        self._log(
            "info",
            f"Uploaded journal file for journal ID {journal_id} with "
            f"{len(self.journal_file_lines)} lines",
        )

        report_file = "".join(
            entry.to_jsonl() for entry in self.journal_file_lines if not entry.is_valid()
        )
        if report_file:
            report_file_name = self._upload_failed_journal_report(journal_id, report_file)
            attachment_link = urljoin(
                self.config.mpt_portal_base_url,
                f"/billing/journals/{journal_id}/attachments",
            )
            send_error(
                SYNCHRONIZATION_ERROR,
                f"Billing journal {journal_id} for {authorization['id']} uploaded with errors.",
                button=Button(f"View errors attached in file {report_file_name}", attachment_link),
            )
        else:
            journal_link = urljoin(
                self.config.mpt_portal_base_url,
                f"/billing/journals/{journal_id}",
            )

            send_success(
                AWS_BILLING_SUCCESS,
                f"Billing journal {journal_id} uploaded for {authorization['id']} "
                f"with {len(self.journal_file_lines)} lines.",
                button=Button(f"Open journal {journal_id}", journal_link),
            )

    def _upload_failed_journal_report(self, journal_id, report_file):
        report_file_name = "ReportJournal.jsonl"
        mimetype = "application/jsonl"
        report = BytesIO(report_file.encode("utf-8"))
        attachment = JournalAttachment(name=report_file_name, description="Failed journal report")
        self.mpt_api_client.billing.journal.attachments(journal_id).upload(
            filename=report_file_name, mimetype=mimetype, file=report, attachment=attachment
        )
        self._log("info", "Uploaded failed journal report")

        return report_file_name

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
        self, subscription, aws_client, journal_details, organization_invoices
    ):
        account_id = subscription.get("externalIds", {}).get("vendor")
        self._log("info", f"Processing subscription for account {account_id}")

        account_metrics = self._get_account_metrics(aws_client, account_id)
        self._get_journal_lines_by_account(
            subscription, account_metrics, journal_details, organization_invoices
        )
        self._manage_invalid_services_by_account(
            account_metrics, journal_details, organization_invoices, account_id
        )
        total_amount = self._calculate_amount_by_account_id(account_id)
        self._log(
            "info",
            f"Generated journal lines for organization account {account_id}: {total_amount}",
        )

    def _calculate_amount_by_account_id(self, account_id):
        total_amount = 0
        for entry in self.journal_file_lines:
            service_account_id = entry.description.value2.split("/")[0]
            if service_account_id == account_id:
                total_amount += entry.price.PPx1
        return total_amount

    def _get_marketplace_usage_report(self, aws_client):
        group_by = [
            {"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"},
            {"Type": "DIMENSION", "Key": "SERVICE"},
        ]
        filter_by = {"Dimensions": {"Key": "BILLING_ENTITY", "Values": [AWS_MARKETPLACE]}}
        return aws_client.get_cost_and_usage(self.start_date, self.end_date, group_by, filter_by)

    def _get_record_type_and_service_cost_by_account_report(self, aws_client, account_id):
        group_by = [
            {"Type": "DIMENSION", "Key": "RECORD_TYPE"},
            {"Type": "DIMENSION", "Key": "SERVICE"},
        ]
        filter_by = {"Dimensions": {"Key": "LINKED_ACCOUNT", "Values": [account_id]}}
        return aws_client.get_cost_and_usage(self.start_date, self.end_date, group_by, filter_by)

    def _get_service_invoice_entity_by_account_id_report(self, aws_client, account_id):
        group_by = [
            {"Type": "DIMENSION", "Key": "SERVICE"},
            {"Type": "DIMENSION", "Key": "INVOICING_ENTITY"},
        ]
        filter_by = {"Dimensions": {"Key": "LINKED_ACCOUNT", "Values": [account_id]}}
        return aws_client.get_cost_and_usage(self.start_date, self.end_date, group_by, filter_by)

    def _get_invoices(self, aws_client, mpa_account):
        invoice_summaries = aws_client.list_invoice_summaries_by_account_id(
            mpa_account, self.year, self.month
        )

        return [invoice for invoice in invoice_summaries if invoice.get("AccountId") == mpa_account]

    def _get_account_metrics(self, aws_client, account_id):
        service_invoice_entity = self._get_service_invoice_entity_by_account_id_report(
            aws_client, account_id
        )
        record_type_report = self._get_record_type_and_service_cost_by_account_report(
            aws_client, account_id
        )
        self.organization_reports["accounts"][account_id] = {
            JournalAttachmentFilesNameEnum.SERVICE_INVOICE_ENTITY.value: service_invoice_entity,
            JournalAttachmentFilesNameEnum.RECORD_TYPE_AND_SERVICE_COST.value: record_type_report,
        }
        return {
            UsageMetricTypeEnum.MARKETPLACE.value: self._get_metrics_by_key(
                self.organization_reports[UsageMetricTypeEnum.MARKETPLACE.value], account_id
            ),
            UsageMetricTypeEnum.SERVICE_INVOICE_ENTITY.value: (
                self._get_invoice_entity_by_service(service_invoice_entity)
            ),
            UsageMetricTypeEnum.USAGE.value: self._get_metrics_by_key(
                record_type_report, AWSRecordTypeEnum.USAGE
            ),
            UsageMetricTypeEnum.SUPPORT.value: self._get_metrics_by_key(
                record_type_report, AWSRecordTypeEnum.SUPPORT
            ),
            UsageMetricTypeEnum.REFUND.value: self._get_metrics_by_key(
                record_type_report, AWSRecordTypeEnum.REFUND
            ),
            UsageMetricTypeEnum.SAVING_PLANS.value: self._get_metrics_by_key(
                record_type_report, AWSRecordTypeEnum.SAVING_PLAN_RECURRING_FEE
            ),
            UsageMetricTypeEnum.PROVIDER_DISCOUNT.value: self._get_metrics_by_key(
                record_type_report, AWSRecordTypeEnum.SOLUTION_PROVIDER_PROGRAM_DISCOUNT
            ),
            UsageMetricTypeEnum.RECURRING.value: self._get_metrics_by_key(
                record_type_report, AWSRecordTypeEnum.RECURRING
            ),
        }

    def _get_journal_lines_by_account(
        self, subscription, account_metrics, journal_details, account_invoices
    ):
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
            except AWSBillingError as ex:
                self._log(
                    "exception",
                    f"Failed to process subscription line {line.get('id')}: {ex}",
                )
                error_line = self._create_line_error(
                    account_id,
                    item_external_id,
                    account_metrics,
                    journal_details,
                    account_invoices,
                    ex.service_name,
                    ex.amount,
                    ex.message,
                )

                self.journal_file_lines.append(error_line)

    @staticmethod
    def _get_invoice_entity_by_service(service_invoice_entity_report):
        result = {}
        for result_by_time in service_invoice_entity_report:
            for group in result_by_time["Groups"]:
                result[group["Keys"][0]] = group["Keys"][1]
        return result

    @staticmethod
    def _get_metrics_by_key(report, key):
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
        journal_details,
        transfer_type,
        organization_invoices,
    ):
        if transfer_type == TransferTypesEnum.SPLIT_BILLING:
            self._log(
                "info",
                f"Skipping MPA account {mpa_account} journal lines generation due to split billing",
            )
            return
        if not first_active_subscription:
            self._log(
                "info", f"No active subscriptions found to report MPA account {mpa_account} usage"
            )
            return

        account_metrics = self._get_account_metrics(aws_client, mpa_account)

        self._get_journal_lines_by_account(
            first_active_subscription,
            account_metrics,
            journal_details,
            organization_invoices,
        )
        self._manage_invalid_services_by_account(
            account_metrics, journal_details, organization_invoices, mpa_account
        )

    @staticmethod
    def _create_line_error(
        account_id,
        item_external_id,
        account_metrics,
        journal_details,
        account_invoices,
        service_name,
        amount,
        error,
    ):
        invoice_entity = account_metrics.get(
            UsageMetricTypeEnum.SERVICE_INVOICE_ENTITY.value, {}
        ).get(service_name, "")
        invoice_id = (
            account_invoices.get("invoice_entities", {}).get(invoice_entity, {}).get("invoice_id")
        )

        return create_journal_line(
            service_name,
            amount,
            item_external_id,
            account_id,
            journal_details,
            invoice_id,
            invoice_entity,
            error=error,
        )

    def _generate_zip(self):
        zip_builder = InMemoryZipBuilder()

        marketplace_report = self.organization_reports.get(
            UsageMetricTypeEnum.MARKETPLACE.value, []
        )
        filename = f"{JournalAttachmentFilesNameEnum.MARKETPLACE_USAGE_REPORT}.json"
        zip_builder.write(filename, json.dumps(marketplace_report, indent=2))

        org_invoices = self.organization_reports.get("invoices", {})
        filename = f"{JournalAttachmentFilesNameEnum.ORGANIZATION_INVOICES}.json"
        zip_builder.write(filename, json.dumps(org_invoices, default=str, indent=2))

        accounts = self.organization_reports.get("accounts", {})
        for account_id, reports in accounts.items():
            for key, value in reports.items():
                filename = f"{account_id} - {key}.json"
                zip_builder.write(filename, json.dumps(value, indent=2))

        return zip_builder.get_file_content()

    def _manage_invalid_services_by_account(
        self, account_metrics, journal_details, account_invoices, account_id
    ):
        account_reports = self.organization_reports["accounts"].get(account_id, {})
        if not account_reports:
            return
        services_by_account = self._get_services_amounts_by_account(account_reports)
        partner_discount = account_metrics.get(UsageMetricTypeEnum.PROVIDER_DISCOUNT.value, {})

        for service, amount in services_by_account.items():
            if not self._service_exists_in_journal_lines(service, account_id):
                service_discount = partner_discount.get(service, 0)
                partner_amount = amount - abs(service_discount)
                discount = ((amount - partner_amount) / amount) * 100 if amount != 0 else 0
                error_msg = (
                    f"{account_id} - Service {service} with amount {amount} and discount "
                    f"{discount} did not match any subscription item."
                )
                self._log("error", error_msg)
                error_line = self._create_line_error(
                    account_id,
                    "Item not found",
                    account_metrics,
                    journal_details,
                    account_invoices,
                    service,
                    amount,
                    error_msg,
                )
                self.journal_file_lines.append(error_line)

    def _service_exists_in_journal_lines(self, service, account_id):
        for line in self.journal_file_lines:
            service_name = line.description.value1
            service_account_id = line.description.value2.split("/")[0]
            mpa_account_id = line.externalIds.vendor
            if service_name == service and account_id in {service_account_id, mpa_account_id}:
                return True
        return False

    @staticmethod
    def _get_services_amounts_by_account(account_reports):
        services_by_account = {}
        record_type = account_reports.get(
            JournalAttachmentFilesNameEnum.RECORD_TYPE_AND_SERVICE_COST.value
        )
        for result_by_time in record_type:
            for group in result_by_time.get("Groups", []):
                service_name = group["Keys"][1]
                if service_name == AWSServiceEnum.TAX:
                    continue

                amount = get_report_amount(
                    group.get("Metrics", {}).get("UnblendedCost", {}).get("Amount", "0")
                )
                if amount > 0:
                    services_by_account[service_name] = amount

        return services_by_account

    def _get_exchange_rate_by_invoice_entity_and_currency(
        self, organization_invoices, invoice_entity
    ):
        """
        Gets the maximum exchange rate for a specific invoicing entity and currency.

        From a list of organization invoice summaries. If no invoices are found for the
        specified invoicing entity, it returns the maximum exchange rate across all invoices
        for the given currency.

        Args:
            organization_invoices (list): List of organization invoice summaries.
            invoice_entity (str): The invoicing entity to filter by.

        Returns:
            float: The maximum exchange rate for the specified invoicing entity,
            or the maximum exchange rate across all invoices if none found.
        """
        exchange_rates = [
            float(
                inv.get("PaymentCurrencyAmount", {})
                .get("CurrencyExchangeDetails", {})
                .get("Rate", 0)
            )
            for inv in organization_invoices
            if inv.get("Entity", {}).get("InvoicingEntity") == invoice_entity
            and inv.get("PaymentCurrencyAmount", {}).get("CurrencyCode", "")
            == self.authorization_currency
        ]
        invoice_entity_exchange_rate = max(exchange_rates, default=0)

        if invoice_entity_exchange_rate == 0:
            exchange_rates = [
                float(
                    inv.get("PaymentCurrencyAmount", {})
                    .get("CurrencyExchangeDetails", {})
                    .get("Rate", 0)
                )
                for inv in organization_invoices
                if inv.get("PaymentCurrencyAmount", {}).get("CurrencyCode", "")
                == self.authorization_currency
            ]
            return max(exchange_rates, default=0)

        return invoice_entity_exchange_rate

    @staticmethod
    def _sum_invoice_amounts(invoices, currency_group, field):
        return sum(float(invoice.get(currency_group, {}).get(field, 0)) for invoice in invoices)

    def _validate_invoice_currencies(
        self, agreement_id, organization_invoices, authorization_currency
    ):
        is_valid = True
        invoice_entities = organization_invoices.get("invoice_entities", {})
        for invoice_entity, invoice_data in invoice_entities.items():
            payment_currency = invoice_data.get("payment_currency_code", "")
            if payment_currency != authorization_currency:
                error_msg = (
                    f"Invoice entity {invoice_entity} has payment currency {payment_currency} "
                    f"which does not match authorization currency {authorization_currency}."
                )
                self._log("error", error_msg)
                send_error(
                    SYNCHRONIZATION_ERROR,
                    f"Failed to generate billing journal for {agreement_id}: {error_msg}",
                )
                is_valid = False

        return is_valid

    def _get_organization_invoices(self, organization_invoices):
        invoice_entities = {}

        for invoice_summary in organization_invoices:
            invoice_entity = invoice_summary.get("Entity", {}).get("InvoicingEntity")
            invoice_id = invoice_summary.get("InvoiceId")
            base_currency = invoice_summary.get("BaseCurrencyAmount", {}).get("CurrencyCode")
            payment_currency = invoice_summary.get("PaymentCurrencyAmount", {}).get(
                "CurrencyCode", ""
            )
            exchange_rate = self._get_exchange_rate_by_invoice_entity_and_currency(
                organization_invoices, invoice_entity
            )

            if invoice_entity in invoice_entities:
                invoice_entities[invoice_entity]["invoice_id"] += f",{invoice_id}"  # noqa: WPS336
            else:
                invoice_entities[invoice_entity] = {
                    "invoice_id": invoice_id,
                    "base_currency_code": base_currency,
                    "payment_currency_code": payment_currency,
                    "exchange_rate": exchange_rate,
                }

        invoices = {
            "invoice_entities": invoice_entities,
            "base_total_amount": self._sum_invoice_amounts(
                organization_invoices, "BaseCurrencyAmount", "TotalAmount"
            ),
            "base_total_amount_before_tax": self._sum_invoice_amounts(
                organization_invoices, "BaseCurrencyAmount", "TotalAmountBeforeTax"
            ),
            "payment_currency_total_amount": self._sum_invoice_amounts(
                organization_invoices, "PaymentCurrencyAmount", "TotalAmount"
            ),
            "payment_currency_total_amount_before_tax": self._sum_invoice_amounts(
                organization_invoices, "PaymentCurrencyAmount", "TotalAmountBeforeTax"
            ),
        }
        self._log(
            "info",
            f"Found {len(organization_invoices)} organization invoice summaries: {invoices}",
        )
        return invoices
