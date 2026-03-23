from decimal import Decimal
from typing import Any, cast, override

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.constants import AWS_MARKETPLACE
from swo_aws_extension.flows.jobs.billing_journal.generators.invoice import InvoiceGenerator
from swo_aws_extension.flows.jobs.billing_journal.generators.report_processor import (
    ReportProcessor,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.usage.generator import (
    BaseOrganizationUsageGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.models.billing_period import BillingPeriod
from swo_aws_extension.flows.jobs.billing_journal.models.invoice import OrganizationInvoice
from swo_aws_extension.flows.jobs.billing_journal.models.usage import (
    AccountUsage,
    OrganizationReport,
    OrganizationUsageResult,
    ServiceMetric,
)
from swo_aws_extension.logger import get_logger

logger = get_logger(__name__)

type BillingView = dict[str, Any]
type ReportRow = dict[str, Any]


class CostExplorerReportFetcher:
    """Fetches cost and usage reports from AWS Cost Explorer."""

    def __init__(self, aws_client: AWSClient) -> None:
        self._aws_client = aws_client

    def get_accounts_with_usage(
        self,
        billing_view: BillingView,
        billing_period: BillingPeriod,
    ) -> list[str]:
        """Get list of accounts with usage for a billing view."""
        cost_and_usage = self._aws_client.get_cost_and_usage(
            start_date=billing_period.start_date,
            end_date=billing_period.end_date,
            view_arn=billing_view.get("arn"),
            group_by=[{"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"}],
        )
        return self._extract_account_keys(cost_and_usage)

    def get_marketplace_usage_report(
        self, billing_view_arn: str, billing_period: BillingPeriod
    ) -> list[ReportRow]:
        """Get marketplace usage report."""
        group_by = [
            {"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"},
            {"Type": "DIMENSION", "Key": "SERVICE"},
        ]
        filter_by = {"Dimensions": {"Key": "BILLING_ENTITY", "Values": [AWS_MARKETPLACE]}}
        return self._aws_client.get_cost_and_usage(
            billing_period.start_date,
            billing_period.end_date,
            group_by,
            filter_by,
            view_arn=billing_view_arn,
        )

    def get_record_type_and_service_cost_report(
        self,
        account_id: str,
        billing_view_arn: str,
        billing_period: BillingPeriod,
    ) -> list[ReportRow]:
        """Get record type and service cost report for an account."""
        group_by = [
            {"Type": "DIMENSION", "Key": "RECORD_TYPE"},
            {"Type": "DIMENSION", "Key": "SERVICE"},
        ]
        filter_by = {"Dimensions": {"Key": "LINKED_ACCOUNT", "Values": [account_id]}}
        return self._aws_client.get_cost_and_usage(
            billing_period.start_date,
            billing_period.end_date,
            group_by,
            filter_by,
            view_arn=billing_view_arn,
        )

    def get_service_invoice_entity_report(
        self,
        account_id: str,
        billing_view_arn: str,
        billing_period: BillingPeriod,
    ) -> list[ReportRow]:
        """Get service invoice entity report for an account."""
        group_by = [
            {"Type": "DIMENSION", "Key": "SERVICE"},
            {"Type": "DIMENSION", "Key": "INVOICING_ENTITY"},
        ]
        filter_by = {"Dimensions": {"Key": "LINKED_ACCOUNT", "Values": [account_id]}}
        return self._aws_client.get_cost_and_usage(
            billing_period.start_date,
            billing_period.end_date,
            group_by,
            filter_by,
            view_arn=billing_view_arn,
        )

    def _extract_account_keys(self, cost_and_usage: list[ReportRow]) -> list[str]:
        keys: list[str] = []
        for period in cost_and_usage:
            for group in period.get("Groups", []):
                keys.extend(group.get("Keys", []))
        return keys


class CostExplorerUsageGenerator(BaseOrganizationUsageGenerator):
    """Implementation for extracting usage using Cost Explorer."""

    def __init__(self, aws_client: AWSClient) -> None:
        super().__init__(aws_client)
        self._report_fetcher: CostExplorerReportFetcher | None = None
        self._organization_invoice = OrganizationInvoice()
        self._processor = ReportProcessor()

    @override
    def run(
        self,
        currency: str,
        mpa_account: str,
        billing_period: BillingPeriod,
        organization_invoice: OrganizationInvoice | None = None,
    ) -> OrganizationUsageResult:  # pyright: ignore[reportImplicitOverride]
        """Extract usage from Cost Explorer and process it.

        Args:
            currency: The authorization currency code.
            mpa_account: The master payer account ID.
            billing_period: The billing period to query.
            organization_invoice: Optional pre-fetched organization invoice metadata.

        Returns:
            OrganizationUsageResult with processed usage data.
        """
        self._usage_by_account = {}
        self._reports = OrganizationReport()

        self._report_fetcher = CostExplorerReportFetcher(self._aws_client)

        if organization_invoice is None:
            invoice_generator = InvoiceGenerator(self._aws_client)
            invoice_result = invoice_generator.run(mpa_account, billing_period, currency)
            self._organization_invoice = invoice_result.invoice
            self._reports.organization_data["INVOICES"] = invoice_result.raw_data
        else:
            self._organization_invoice = organization_invoice

        logger.info(
            "Found %d invoice entities",
            len(self._organization_invoice.entities),
        )

        billing_views = cast(
            list[BillingView],
            self._aws_client.get_billing_views_by_account_id(
                mpa_account,
                start_date=billing_period.start_date,
                end_date=billing_period.last_day,
            ),
        )
        logger.info(
            "Found %d billing view exports for account %s",
            len(billing_views),
            mpa_account,
        )

        for index, billing_view in enumerate(billing_views, start=1):
            logger.info(
                "Processing billing view export %d of %d",
                index,
                len(billing_views),
            )
            self._process_billing_view(billing_view, billing_period)

        return OrganizationUsageResult(
            reports=self._reports, usage_by_account=self._usage_by_account
        )

    def _process_billing_view(
        self,
        billing_view: BillingView,
        billing_period: BillingPeriod,
    ) -> None:
        view_arn = billing_view.get("arn")
        logger.info(
            "Processing billing view export %s for billing period %s",
            view_arn,
            billing_period,
        )
        report_fetcher = self._report_fetcher
        if report_fetcher is None:
            logger.warning(
                "Skipping billing view export %s - Report fetcher is not initialized",
                view_arn,
            )
            return
        try:
            accounts = report_fetcher.get_accounts_with_usage(billing_view, billing_period)
            logger.info(
                "Retrieved %d accounts with usage for billing view export %s",
                len(accounts),
                view_arn,
            )
        except AWSError as error:
            logger.warning(
                "Skipping billing view export %s - Error retrieving accounts with usage: %s",
                view_arn,
                error,
            )
            return

        marketplace_report = report_fetcher.get_marketplace_usage_report(
            view_arn, billing_period
        )
        self._reports.organization_data["MARKETPLACE"] = marketplace_report

        self._process_accounts_for_billing_view(
            accounts, billing_view, billing_period, marketplace_report
        )
        logger.info(
            "Successfully processed billing view export %s",
            view_arn,
        )

    def _process_accounts_for_billing_view(
        self,
        accounts: list[str],
        billing_view: BillingView,
        billing_period: BillingPeriod,
        marketplace_report: list[ReportRow],
    ) -> None:
        report_fetcher = self._report_fetcher
        if report_fetcher is None:
            return
        for account_id in accounts:
            logger.info("Getting usage for account: %s", account_id)
            if account_id not in self._reports.accounts_data:
                self._reports.accounts_data[account_id] = {}

            service_invoice_entity = report_fetcher.get_service_invoice_entity_report(
                account_id, billing_view.get("arn"), billing_period
            )
            self._reports.accounts_data[account_id]["SERVICE_INVOICE_ENTITY"] = (
                service_invoice_entity
            )

            record_type_report = report_fetcher.get_record_type_and_service_cost_report(
                account_id, billing_view.get("arn"), billing_period
            )
            self._reports.accounts_data[account_id]["RECORD_TYPE_AND_SERVICE_COST"] = (
                record_type_report
            )

            self._usage_by_account[account_id] = self._get_account_usage(
                account_id,
                marketplace_report,
                service_invoice_entity,
                record_type_report,
            )

    def _get_account_usage(
        self,
        account_id: str,
        marketplace_report: list[ReportRow],
        service_invoice_entity: list[ReportRow],
        record_type_report: list[ReportRow],
    ) -> AccountUsage:
        invoice_entities = self._processor.extract_invoice_entities(service_invoice_entity)

        account_usage = AccountUsage()
        marketplace_metrics = self._processor.extract_metrics(marketplace_report, account_id)
        all_metrics = self._processor.extract_all_metrics_by_record_type(record_type_report)

        self._add_metrics_to_account_usage(
            account_usage,
            marketplace_metrics,
            all_metrics,
            invoice_entities,
        )

        return account_usage

    def _add_metrics_to_account_usage(
        self,
        account_usage: AccountUsage,
        marketplace_metrics: dict[str, Decimal],
        all_metrics: dict[str, dict[str, Decimal]],
        invoice_entities: dict[str, str],
    ) -> None:
        for service_name, amount in marketplace_metrics.items():
            invoice_entity_name = invoice_entities.get(service_name)
            invoice_entity = self._organization_invoice.entities.get(invoice_entity_name or "")
            metric = ServiceMetric(
                service_name=service_name,
                record_type="MARKETPLACE",
                amount=amount,
                invoice_entity=invoice_entity_name,
                invoice_id=invoice_entity.invoice_id if invoice_entity else None,
            )
            account_usage.add_metric(metric)

        for record_type, metrics in all_metrics.items():
            for service_name, amount in metrics.items():
                invoice_entity_name = invoice_entities.get(service_name)
                invoice_entity = self._organization_invoice.entities.get(invoice_entity_name or "")
                metric = ServiceMetric(
                    service_name=service_name,
                    record_type=record_type,
                    amount=amount,
                    invoice_entity=invoice_entity_name,
                    invoice_id=invoice_entity.invoice_id if invoice_entity else None,
                )
                account_usage.add_metric(metric)
