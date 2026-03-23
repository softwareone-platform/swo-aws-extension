import io
import types
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, override

import pyarrow as pa
from pyarrow import parquet as pq

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.constants import AWS_MARKETPLACE, AWSRecordTypeEnum
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

type ReportRow = dict[str, Any]

PARQUET_RECORD_TYPE_MAP: Mapping[str, str] = types.MappingProxyType({
    "Usage": AWSRecordTypeEnum.USAGE,
    "SppDiscount": AWSRecordTypeEnum.SOLUTION_PROVIDER_PROGRAM_DISCOUNT,
    "Tax": "Tax",
    "Refund": AWSRecordTypeEnum.REFUND,
    "Support": AWSRecordTypeEnum.SUPPORT,
    "SavingsPlanRecurringFee": AWSRecordTypeEnum.SAVING_PLAN_RECURRING_FEE,
    "Recurring": AWSRecordTypeEnum.RECURRING,
    "Credit": AWSRecordTypeEnum.CREDIT,
})

_BILLING_PERIOD_PREFIX = "BILLING_PERIOD%3D"
_PARQUET_SUFFIX = ".parquet"

_COL_ACCOUNT_ID = "line_item_usage_account_id"
_COL_PRODUCT_CODE = "line_item_product_code"
_COL_LINE_ITEM_TYPE = "line_item_line_item_type"
_COL_UNBLENDED_COST = "line_item_unblended_cost"
_COL_INVOICING_ENTITY = "bill_invoicing_entity"
_COL_INVOICE_ID = "bill_invoice_id"
_COL_BILLING_ENTITY = "bill_billing_entity"


@dataclass(frozen=True)
class _MetricKey:
    account_id: str
    service_name: str
    record_type: str
    invoice_entity: str | None
    invoice_id: str | None


def _parse_cost(cost_value: object | None) -> Decimal:
    """Convert a raw parquet cost value to a Decimal.

    Args:
        cost_value: The raw value from the parquet ``line_item_unblended_cost`` column.

    Returns:
        A Decimal representation of the cost, defaulting to zero for None values.
    """
    return Decimal(0) if cost_value is None else Decimal(str(cost_value))


def _resolve_record_type(raw_type: str, billing_entity: str) -> str:
    """Map a parquet line item type to a ServiceMetric record type.

    Args:
        raw_type: The raw ``line_item_line_item_type`` value from the parquet row.
        billing_entity: The ``bill_billing_entity`` value; used to detect marketplace rows.

    Returns:
        The normalised record type string for use in ServiceMetric.
    """
    if billing_entity == AWS_MARKETPLACE:
        return "MARKETPLACE"
    return str(PARQUET_RECORD_TYPE_MAP.get(raw_type, raw_type))


def _build_metric_key(row: ReportRow) -> _MetricKey | None:
    """Parse a parquet row into a _MetricKey, or return None if the row is invalid.

    Args:
        row: A parquet row as a plain dict.

    Returns:
        A _MetricKey if the row contains the required fields, else None.
    """
    account_id = row.get(_COL_ACCOUNT_ID) or ""
    service_name = row.get(_COL_PRODUCT_CODE) or ""
    if not account_id or not service_name:
        return None
    raw_type = row.get(_COL_LINE_ITEM_TYPE) or ""
    billing_entity = row.get(_COL_BILLING_ENTITY) or ""
    record_type = _resolve_record_type(raw_type, billing_entity)
    return _MetricKey(
        account_id=account_id,
        service_name=service_name,
        record_type=record_type,
        invoice_entity=row.get(_COL_INVOICING_ENTITY) or None,
        invoice_id=row.get(_COL_INVOICE_ID) or None,
    )


class S3ParquetReportFetcher:
    """Lists and downloads parquet billing reports from S3 for a given billing period."""

    def __init__(self, aws_client: AWSClient, s3_bucket: str, s3_prefix: str) -> None:
        self._aws_client = aws_client
        self._s3_bucket = s3_bucket
        self._s3_prefix = s3_prefix

    @property
    def s3_bucket(self) -> str:
        """Return the configured S3 bucket name."""
        return self._s3_bucket

    @property
    def s3_prefix(self) -> str:
        """Return the configured S3 key prefix."""
        return self._s3_prefix

    def list_billing_period_keys(self, billing_period: BillingPeriod) -> list[str]:
        """List S3 keys for all parquet files matching the billing period.

        Args:
            billing_period: The billing period to filter by.

        Returns:
            List of S3 object keys for matching parquet files.
        """
        period_segment = self._billing_period_segment(billing_period)
        all_keys = self._aws_client.list_s3_objects(self._s3_bucket, self._s3_prefix)
        return [key for key in all_keys if period_segment in key and key.endswith(_PARQUET_SUFFIX)]

    def download_parquet_table(self, key: str) -> pa.Table:
        """Download a parquet file from S3 and return it as a pyarrow Table.

        Args:
            key: The S3 object key to download.

        Returns:
            A pyarrow Table with the parquet contents.
        """
        raw_bytes = self._aws_client.download_s3_object(self._s3_bucket, key)
        return pq.read_table(io.BytesIO(raw_bytes))

    def _billing_period_segment(self, billing_period: BillingPeriod) -> str:
        month_str = str(billing_period.month).zfill(2)
        return f"{_BILLING_PERIOD_PREFIX}{billing_period.year}-{month_str}"


class CostUsageReportGenerator(BaseOrganizationUsageGenerator):
    """Extracts organization usage from customer usage reports stored in S3 as parquet files."""

    def __init__(self, aws_client: AWSClient, s3_bucket: str, s3_prefix: str) -> None:
        super().__init__(aws_client)
        self._fetcher = S3ParquetReportFetcher(aws_client, s3_bucket, s3_prefix)

    @override
    def run(
        self,
        currency: str,
        mpa_account: str,
        billing_period: BillingPeriod,
        organization_invoice: OrganizationInvoice | None = None,
    ) -> OrganizationUsageResult:
        """Extract usage from S3 parquet files and build an OrganizationUsageResult.

        Args:
            currency: The authorization currency code (unused; present for interface compat).
            mpa_account: The master payer account ID (unused; present for interface compat).
            billing_period: The billing period to process.
            organization_invoice: Unused pre-fetched invoice metadata kept for interface
                compatibility.

        Returns:
            OrganizationUsageResult with processed usage data grouped by account.
        """
        self._usage_by_account = {}
        self._reports = OrganizationReport()

        keys = self._fetcher.list_billing_period_keys(billing_period)
        if not keys:
            logger.info(
                "No parquet files found for billing period %s under s3://%s/%s",
                billing_period.start_date,
                self._fetcher.s3_bucket,
                self._fetcher.s3_prefix,
            )
            return OrganizationUsageResult(
                reports=self._reports, usage_by_account=self._usage_by_account
            )

        logger.info("Found %d parquet file(s) for billing period %s", len(keys), billing_period)

        rows = self._load_all_rows(keys)
        self._process_rows(rows)

        return OrganizationUsageResult(
            reports=self._reports, usage_by_account=self._usage_by_account
        )

    def _load_all_rows(self, keys: list[str]) -> list[ReportRow]:
        """Download and concatenate all parquet files into a flat list of row dicts."""
        rows: list[ReportRow] = []
        for key in keys:
            logger.info("Downloading parquet file: %s", key)
            rows.extend(self._table_to_rows(self._fetcher.download_parquet_table(key)))
        return rows

    def _table_to_rows(self, table: pa.Table) -> list[ReportRow]:
        """Convert a pyarrow Table into a list of row dictionaries."""
        rows: list[ReportRow] = []
        for batch in table.to_batches():
            columns = batch.column_names
            batch_dict = batch.to_pydict()
            rows.extend(
                {col: batch_dict[col][row_index] for col in columns}
                for row_index in range(batch.num_rows)
            )
        return rows

    def _process_rows(self, rows: list[ReportRow]) -> None:
        """Convert rows into AccountUsage metrics grouped by account ID."""
        for row in rows:
            metric_key = _build_metric_key(row)
            if metric_key is None:
                continue
            amount = _parse_cost(row.get(_COL_UNBLENDED_COST))
            if amount == Decimal(0):
                continue
            self._add_metric_to_account(metric_key, amount)

    def _add_metric_to_account(self, metric_key: _MetricKey, amount: Decimal) -> None:
        """Create a ServiceMetric and add it to the appropriate AccountUsage.

        Args:
            metric_key: Identifies the account, service, and record type.
            amount: Row-level cost amount.
        """
        metric = ServiceMetric(
            service_name=metric_key.service_name,
            record_type=metric_key.record_type,
            amount=amount,
            invoice_entity=metric_key.invoice_entity,
            invoice_id=metric_key.invoice_id,
        )
        self._usage_by_account.setdefault(metric_key.account_id, AccountUsage()).add_metric(metric)
