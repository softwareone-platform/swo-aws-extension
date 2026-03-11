from abc import ABC, abstractmethod
from decimal import Decimal

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.constants import AWS_MARKETPLACE, DEC_ZERO, AWSRecordTypeEnum
from swo_aws_extension.flows.jobs.billing_journal.models.billing_period import BillingPeriod
from swo_aws_extension.flows.jobs.billing_journal.models.usage import (
    AccountUsage,
    OrganizationReport,
    OrganizationUsageResult,
    ServiceUsage,
)
from swo_aws_extension.logger import get_logger

logger = get_logger(__name__)


class CostExplorerReportFetcher:
    """Fetches cost and usage reports from AWS Cost Explorer."""

    def __init__(self, aws_client: AWSClient) -> None:
        self._aws_client = aws_client

    def get_accounts_with_usage(
        self,
        billing_view: dict,
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
    ) -> list[dict]:
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
    ) -> list[dict]:
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
    ) -> list[dict]:
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
        self, agreement_id: str, mpa_account: str, billing_period: BillingPeriod
    ) -> OrganizationUsageResult:
        """Extract RAW information and process it into AccountUsage."""


class CostExplorerUsageGenerator(BaseOrganizationUsageGenerator):
    """Implementation for extracting usage using Cost Explorer."""

    def __init__(self, aws_client):
        super().__init__(aws_client)
        self._report_fetcher = None

    def run(
        self, agreement_id: str, mpa_account: str, billing_period: BillingPeriod
    ) -> OrganizationUsageResult:
        """Extract usage from Cost Explorer and process it."""
        self._usage_by_account = {}
        self._reports = OrganizationReport()

        self._report_fetcher = CostExplorerReportFetcher(self._aws_client)
        billing_views = self._aws_client.get_billing_views_by_account_id(
            mpa_account,
            start_date=billing_period.start_date,
            end_date=billing_period.last_day,
        )
        logger.info("Found %d billing views for agreement %s", len(billing_views), agreement_id)

        for billing_view in billing_views:
            self._process_billing_view(billing_view, billing_period)

        return OrganizationUsageResult(
            reports=self._reports, usage_by_account=self._usage_by_account
        )

    def _process_billing_view(
        self,
        billing_view: dict,
        billing_period: BillingPeriod,
    ) -> None:
        try:
            accounts = self._report_fetcher.get_accounts_with_usage(billing_view, billing_period)
        except AWSError as error:
            logger.info(
                "Error retrieving accounts with usage for billing view %s: %s",
                billing_view.get("arn"),
                error,
            )
            return

        marketplace_report = self._report_fetcher.get_marketplace_usage_report(
            billing_view.get("arn"), billing_period
        )

        self._reports.organization_data["MARKETPLACE"] = (
            self._reports.organization_data.get("MARKETPLACE", []) + marketplace_report
        )

        for account_id in accounts:
            logger.info("Getting usage for account: %s", account_id)
            if account_id not in self._reports.accounts_data:
                self._reports.accounts_data[account_id] = {}

            service_invoice_entity = self._report_fetcher.get_service_invoice_entity_report(
                account_id, billing_view.get("arn"), billing_period
            )
            self._reports.accounts_data[account_id]["SERVICE_INVOICE_ENTITY"] = (
                service_invoice_entity
            )

            record_type_report = self._report_fetcher.get_record_type_and_service_cost_report(
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
        marketplace_report: list[dict],
        service_invoice_entity: list[dict],
        record_type_report: list[dict],
    ) -> AccountUsage:
        metrics = {
            "marketplace": self._extract_metrics(marketplace_report, account_id),
            "invoice_entity": self._extract_invoice_entities(service_invoice_entity),
            "provider": self._extract_metrics(
                record_type_report, AWSRecordTypeEnum.SOLUTION_PROVIDER_PROGRAM_DISCOUNT
            ),
            "usage": self._extract_metrics(record_type_report, AWSRecordTypeEnum.USAGE),
            "support": self._extract_metrics(record_type_report, AWSRecordTypeEnum.SUPPORT),
            "refund": self._extract_metrics(record_type_report, AWSRecordTypeEnum.REFUND),
            "saving": self._extract_metrics(
                record_type_report, AWSRecordTypeEnum.SAVING_PLAN_RECURRING_FEE
            ),
            "recurring": self._extract_metrics(record_type_report, AWSRecordTypeEnum.RECURRING),
        }

        all_services: set[str] = set()
        for metric_data in metrics.values():
            all_services.update(metric_data.keys())

        services: dict[str, ServiceUsage] = {}

        for service in all_services:
            services[service] = ServiceUsage(
                marketplace=metrics["marketplace"].get(service, DEC_ZERO),
                service_invoice_entity=metrics["invoice_entity"].get(service),
                provider_discount=metrics["provider"].get(service, DEC_ZERO),
                usage=metrics["usage"].get(service, DEC_ZERO),
                support=metrics["support"].get(service, DEC_ZERO),
                refund=metrics["refund"].get(service, DEC_ZERO),
                saving_plans=metrics["saving"].get(service, DEC_ZERO),
                recurring=metrics["recurring"].get(service, DEC_ZERO),
            )

        return AccountUsage(services=services)

    def _extract_invoice_entities(self, report: list[dict]) -> dict[str, str]:
        result: dict[str, str] = {}
        for result_by_time in report:
            for group in result_by_time.get("Groups", []):
                keys = group.get("Keys", [])
                if len(keys) >= 2:
                    result[keys[0]] = keys[1]
        return result

    def _extract_metrics(self, report: list[dict], key: str) -> dict[str, Decimal]:
        result: dict[str, Decimal] = {}
        for result_by_time in report:
            for group in result_by_time.get("Groups", []):
                keys = group.get("Keys", [])
                if key not in keys:
                    continue
                amount = self._parse_amount(
                    group.get("Metrics", {}).get("UnblendedCost", {}).get("Amount", "0")
                )
                if amount != Decimal(0):
                    result[keys[1]] = amount
        return result

    def _parse_amount(self, amount: str) -> Decimal:
        """Convert a string amount to Decimal, handling comma and dot separators."""
        return Decimal(amount.replace(",", ".") if "," in amount else amount)
