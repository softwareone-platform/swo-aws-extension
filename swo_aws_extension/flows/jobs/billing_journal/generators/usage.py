from abc import ABC, abstractmethod

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.constants import AWS_MARKETPLACE
from swo_aws_extension.flows.jobs.billing_journal.generators.report_processor import (
    ReportProcessor,
)
from swo_aws_extension.flows.jobs.billing_journal.models.billing_period import BillingPeriod
from swo_aws_extension.flows.jobs.billing_journal.models.invoice import OrganizationInvoice
from swo_aws_extension.flows.jobs.billing_journal.models.usage import (
    AccountUsage,
    ExtractedMetric,
    OrganizationReport,
    OrganizationUsageResult,
    ServiceMetric,
)
from swo_aws_extension.logger import get_logger

logger = get_logger(__name__)


def _marketplace_billing_entity_filter() -> dict:
    return {"Dimensions": {"Key": "BILLING_ENTITY", "Values": [AWS_MARKETPLACE]}}


class CostExplorerReportFetcher:
    """Fetches cost and usage reports from AWS Cost Explorer."""

    def __init__(self, aws_client: AWSClient) -> None:
        self._aws_client = aws_client

    def get_accounts_with_usage(
        self,
        billing_view_arn: str,
        billing_period: BillingPeriod,
    ) -> list[str]:
        """Get list of accounts with usage for a billing view."""
        cost_and_usage = self._aws_client.get_cost_and_usage(
            billing_period=billing_period,
            view_arn=billing_view_arn,
            group_by=[{"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"}],
        )
        return self._extract_account_keys(cost_and_usage)

    def get_marketplace_usage_report(
        self, billing_view_arn: str, billing_period: BillingPeriod, granularity: str = "DAILY"
    ) -> list[dict]:
        """Get marketplace usage report."""
        group_by = [
            {"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"},
            {"Type": "DIMENSION", "Key": "SERVICE"},
        ]
        filter_by = _marketplace_billing_entity_filter()
        return self._aws_client.get_cost_and_usage(
            billing_period,
            group_by,
            filter_by,
            view_arn=billing_view_arn,
            granularity=granularity,
        )

    def get_record_type_and_service_cost_report(
        self,
        account_id: str,
        billing_view_arn: str,
        billing_period: BillingPeriod,
        granularity: str = "DAILY",
    ) -> list[dict]:
        """Get record type and service cost report for an account."""
        group_by = [
            {"Type": "DIMENSION", "Key": "RECORD_TYPE"},
            {"Type": "DIMENSION", "Key": "SERVICE"},
        ]
        filter_by = {
            "And": [
                {"Dimensions": {"Key": "LINKED_ACCOUNT", "Values": [account_id]}},
                {"Not": _marketplace_billing_entity_filter()},
            ]
        }
        return self._aws_client.get_cost_and_usage(
            billing_period,
            group_by,
            filter_by,
            view_arn=billing_view_arn,
            granularity=granularity,
        )

    def get_service_invoice_entity_report(
        self,
        account_id: str,
        billing_view_arn: str,
        billing_period: BillingPeriod,
        granularity: str = "DAILY",
    ) -> list[dict]:
        """Get service invoice entity report for an account."""
        group_by = [
            {"Type": "DIMENSION", "Key": "SERVICE"},
            {"Type": "DIMENSION", "Key": "INVOICING_ENTITY"},
        ]
        filter_by = {"Dimensions": {"Key": "LINKED_ACCOUNT", "Values": [account_id]}}
        return self._aws_client.get_cost_and_usage(
            billing_period,
            group_by,
            filter_by,
            view_arn=billing_view_arn,
            granularity=granularity,
        )

    def _extract_account_keys(self, cost_and_usage: list[dict]) -> list[str]:
        keys: list[str] = []
        for period in cost_and_usage:
            for group in period.get("Groups", []):
                keys.extend(group.get("Keys", []))
        return keys


class BaseOrganizationUsageGenerator(ABC):
    """Base interface for extracting organization usage (Cost Explorer, CUR, etc.)."""

    def __init__(self, aws_client) -> None:
        self._aws_client = aws_client
        self._reports = OrganizationReport()
        self._usage_by_account: dict[str, AccountUsage] = {}

    @abstractmethod
    def run(
        self,
        currency: str,
        mpa_account: str,
        billing_period: BillingPeriod,
        organization_invoice: OrganizationInvoice,
        granularity: str = "DAILY",
    ) -> OrganizationUsageResult:
        """Extract RAW information and process it into AccountUsage."""

    @abstractmethod
    def run_for_pma(
        self,
        pma_account: str,
        billing_period: BillingPeriod,
        organization_invoice: OrganizationInvoice,
        granularity: str = "DAILY",
    ) -> OrganizationUsageResult:
        """Extract RAW information and process it for the PMA account."""


class CostExplorerUsageGenerator(BaseOrganizationUsageGenerator):
    """Implementation for extracting usage using Cost Explorer."""

    def __init__(self, aws_client):
        super().__init__(aws_client)
        self._organization_invoice: OrganizationInvoice | None = None
        self._report_fetcher = None
        self._processor = ReportProcessor()

    def run(
        self,
        currency: str,
        mpa_account: str,
        billing_period: BillingPeriod,
        organization_invoice: OrganizationInvoice,
        granularity: str = "DAILY",
    ) -> OrganizationUsageResult:
        """Extract usage from Cost Explorer and process it."""
        self._usage_by_account = {}
        self._reports = OrganizationReport()
        self._organization_invoice = organization_invoice

        logger.info("Generating usage report for MPA account %s", mpa_account)
        self._report_fetcher = CostExplorerReportFetcher(self._aws_client)

        billing_views = self._aws_client.get_billing_views_by_account_id(
            mpa_account,
            start_date=billing_period.start_date,
            end_date=billing_period.last_day,
        )
        logger.info("Found %d billing views", len(billing_views))

        for billing_view in billing_views:
            self._process_billing_view(billing_view, billing_period, granularity)

        return OrganizationUsageResult(
            reports=self._reports, usage_by_account=self._usage_by_account
        )

    def run_for_pma(
        self,
        pma_account: str,
        billing_period: BillingPeriod,
        organization_invoice: OrganizationInvoice,
        granularity: str = "DAILY",
    ) -> OrganizationUsageResult:
        """Extract usage from Cost Explorer for the PMA account and process it."""
        self._usage_by_account = {}
        self._reports = OrganizationReport()
        self._organization_invoice = organization_invoice

        logger.info("Generating usage report for PMA account %s", pma_account)
        self._report_fetcher = CostExplorerReportFetcher(self._aws_client)

        marketplace_report = self._report_fetcher.get_marketplace_usage_report(
            "", billing_period, granularity
        )
        self._reports.organization_data["MARKETPLACE"] = marketplace_report

        self._process_accounts_for_billing_view(
            [pma_account], {"arn": None}, billing_period, marketplace_report, granularity
        )

        return OrganizationUsageResult(
            reports=self._reports, usage_by_account=self._usage_by_account
        )

    def _process_billing_view(
        self,
        billing_view: dict,
        billing_period: BillingPeriod,
        granularity: str,
    ) -> None:
        try:
            accounts = self._report_fetcher.get_accounts_with_usage(
                billing_view.get("arn"), billing_period
            )
        except AWSError as error:
            logger.info(
                "Error retrieving accounts with usage for billing view %s: %s",
                billing_view.get("arn"),
                error,
            )
            return
        logger.info(
            "Found %d accounts with usage for billing view %s",
            len(accounts),
            billing_view.get("arn"),
        )
        marketplace_report = self._report_fetcher.get_marketplace_usage_report(
            billing_view.get("arn"), billing_period, granularity
        )
        self._reports.organization_data["MARKETPLACE"] = marketplace_report

        self._process_accounts_for_billing_view(
            accounts, billing_view, billing_period, marketplace_report, granularity
        )

    def _process_accounts_for_billing_view(
        self,
        accounts: list[str],
        billing_view: dict,
        billing_period: BillingPeriod,
        marketplace_report: list[dict],
        granularity: str,
    ) -> None:
        for account_id in accounts:
            logger.info("Getting usage for account: %s", account_id)
            if account_id not in self._reports.accounts_data:
                self._reports.accounts_data[account_id] = {}

            service_invoice_entity = self._report_fetcher.get_service_invoice_entity_report(
                account_id, billing_view.get("arn"), billing_period, granularity
            )
            self._reports.accounts_data[account_id]["SERVICE_INVOICE_ENTITY"] = (
                service_invoice_entity
            )

            record_type_report = self._report_fetcher.get_record_type_and_service_cost_report(
                account_id, billing_view.get("arn"), billing_period, granularity
            )
            self._reports.accounts_data[account_id]["RECORD_TYPE_AND_SERVICE_COST"] = (
                record_type_report
            )
            self._usage_by_account[account_id] = self._build_account_usage(
                account_id,
                marketplace_report,
                record_type_report,
                self._processor.extract_invoice_entities(service_invoice_entity),
            )

    def _build_account_usage(
        self,
        account_id: str,
        marketplace_report: list[dict],
        record_type_report: list[dict],
        entities: dict[str, str],
    ) -> AccountUsage:
        account_usage = AccountUsage()
        for metric_data in self._processor.extract_metrics(
            marketplace_report,
            account_id,
        ):
            account_usage.add_metric(
                self._create_metric(metric_data, "MARKETPLACE", entities),
            )
        for rt_data in self._processor.extract_all_metrics_by_record_type(
            record_type_report,
        ):
            account_usage.add_metric(
                self._create_metric(rt_data, rt_data.record_type, entities),
            )

        return account_usage

    def _create_metric(
        self,
        metric_data: ExtractedMetric,
        record_type: str,
        entities: dict[str, str],
    ) -> ServiceMetric:

        entity_name = entities.get(metric_data.service_name)
        invoice_entity = self._organization_invoice.entities.get(entity_name, None)
        return ServiceMetric(
            service_name=metric_data.service_name,
            record_type=record_type,
            amount=metric_data.amount,
            invoice_entity=entity_name,
            invoice_id=invoice_entity.invoice_id if invoice_entity else "",
            start_date=metric_data.start_date,
            end_date=metric_data.end_date,
        )
