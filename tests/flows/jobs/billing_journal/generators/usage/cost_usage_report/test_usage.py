import io
from decimal import Decimal

import pyarrow as pa
import pytest
from pyarrow import parquet as pq

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.constants import AWSRecordTypeEnum
from swo_aws_extension.flows.jobs.billing_journal.generators.usage.cost_usage_report.usage import (
    CostUsageReportGenerator,
    S3ParquetReportFetcher,
)
from swo_aws_extension.flows.jobs.billing_journal.models.billing_period import BillingPeriod
from swo_aws_extension.flows.jobs.billing_journal.models.usage import (
    OrganizationUsageResult,
    ServiceMetric,
)

MODULE = "swo_aws_extension.flows.jobs.billing_journal.generators.usage.cost_usage_report.usage"

S3_BUCKET = "my-billing-bucket"
S3_PREFIX = "billing/exports"
MPA_ACCOUNT = "123456789012"


def _make_parquet_bytes(rows: list[dict]) -> bytes:
    """Build an in-memory parquet file from a list of row dicts."""
    if rows:
        columns = list(rows[0].keys())
        arrays = {col: [row.get(col) for row in rows] for col in columns}
        table = pa.table(arrays)
    else:
        schema = pa.schema([
            pa.field("line_item_usage_account_id", pa.string()),
            pa.field("line_item_product_code", pa.string()),
            pa.field("line_item_line_item_type", pa.string()),
            pa.field("line_item_unblended_cost", pa.float64()),
            pa.field("bill_invoicing_entity", pa.string()),
            pa.field("bill_invoice_id", pa.string()),
            pa.field("bill_billing_entity", pa.string()),
        ])
        table = pa.table({schema_field.name: [] for schema_field in schema}, schema=schema)
    buf = io.BytesIO()
    pq.write_table(table, buf)
    return buf.getvalue()


@pytest.fixture
def mock_aws_client(mocker):
    return mocker.MagicMock(spec=AWSClient)


@pytest.fixture
def billing_period():
    return BillingPeriod(start_date="2026-03-01", end_date="2026-04-01")


@pytest.fixture
def generator(mock_aws_client):
    return CostUsageReportGenerator(mock_aws_client, S3_BUCKET, S3_PREFIX)


@pytest.fixture
def sample_rows():
    return [
        {
            "line_item_usage_account_id": "111111111111",
            "line_item_product_code": "AmazonEC2",
            "line_item_line_item_type": "Usage",
            "line_item_unblended_cost": 50.0,
            "bill_invoicing_entity": "Amazon Web Services, Inc.",
            "bill_invoice_id": None,
            "bill_billing_entity": "AWS",
        },
        {
            "line_item_usage_account_id": "111111111111",
            "line_item_product_code": "AmazonEC2",
            "line_item_line_item_type": "Usage",
            "line_item_unblended_cost": 25.0,
            "bill_invoicing_entity": "Amazon Web Services, Inc.",
            "bill_invoice_id": None,
            "bill_billing_entity": "AWS",
        },
    ]


@pytest.fixture
def sample_parquet_bytes(sample_rows):
    return _make_parquet_bytes(sample_rows)


def test_list_billing_period_keys_filters_by_period(mock_aws_client, billing_period):
    mock_aws_client.list_s3_objects.return_value = [
        f"{S3_PREFIX}/acct/view/data/BILLING_PERIOD%3D2026-03/report-00001.snappy.parquet",
        f"{S3_PREFIX}/acct/view/data/BILLING_PERIOD%3D2026-02/report-00001.snappy.parquet",
        f"{S3_PREFIX}/acct/view/data/BILLING_PERIOD%3D2026-03/report-00002.snappy.parquet",
        f"{S3_PREFIX}/acct/view/data/BILLING_PERIOD%3D2026-03/manifest.json",
    ]
    fetcher = S3ParquetReportFetcher(mock_aws_client, S3_BUCKET, S3_PREFIX)

    result = fetcher.list_billing_period_keys(billing_period)

    assert len(result) == 2
    assert all("BILLING_PERIOD%3D2026-03" in key for key in result)
    assert all(key.endswith(".parquet") for key in result)


def test_list_billing_period_keys_returns_empty_when_no_match(mock_aws_client, billing_period):
    mock_aws_client.list_s3_objects.return_value = [
        f"{S3_PREFIX}/acct/view/data/BILLING_PERIOD%3D2026-02/report-00001.snappy.parquet",
    ]
    fetcher = S3ParquetReportFetcher(mock_aws_client, S3_BUCKET, S3_PREFIX)

    result = fetcher.list_billing_period_keys(billing_period)

    assert result == []


def test_init_uses_constructor_parameters_for_s3_lookup(mock_aws_client, billing_period):
    generator = CostUsageReportGenerator(mock_aws_client, S3_BUCKET, S3_PREFIX)
    mock_aws_client.list_s3_objects.return_value = []

    generator.run("USD", MPA_ACCOUNT, billing_period)  # act

    mock_aws_client.list_s3_objects.assert_called_once_with(S3_BUCKET, S3_PREFIX)


def test_run_returns_empty_when_no_keys_found(generator, mock_aws_client, billing_period):
    mock_aws_client.list_s3_objects.return_value = []

    result = generator.run("USD", MPA_ACCOUNT, billing_period)

    assert isinstance(result, OrganizationUsageResult)
    assert result.usage_by_account == {}


def test_run_preserves_row_level_usage_metrics(
    generator, mock_aws_client, billing_period, sample_parquet_bytes
):
    key = f"{S3_PREFIX}/acct/view/data/BILLING_PERIOD%3D2026-03/report-00001.snappy.parquet"
    mock_aws_client.list_s3_objects.return_value = [key]
    mock_aws_client.download_s3_object.return_value = sample_parquet_bytes

    result = generator.run("USD", MPA_ACCOUNT, billing_period)

    account_usage = result.usage_by_account.get("111111111111")
    assert account_usage is not None
    assert len(account_usage.metrics) == 2
    assert account_usage.metrics[0] == ServiceMetric(
        service_name="AmazonEC2",
        record_type=AWSRecordTypeEnum.USAGE,
        amount=Decimal("50.0"),
        invoice_entity="Amazon Web Services, Inc.",
        invoice_id=None,
    )
    assert account_usage.metrics[1] == ServiceMetric(
        service_name="AmazonEC2",
        record_type=AWSRecordTypeEnum.USAGE,
        amount=Decimal("25.0"),
        invoice_entity="Amazon Web Services, Inc.",
        invoice_id=None,
    )


def test_run_sets_invoice_entity_from_rows(
    generator, mock_aws_client, billing_period, sample_parquet_bytes
):
    key = f"{S3_PREFIX}/acct/view/data/BILLING_PERIOD%3D2026-03/report-00001.snappy.parquet"
    mock_aws_client.list_s3_objects.return_value = [key]
    mock_aws_client.download_s3_object.return_value = sample_parquet_bytes

    result = generator.run("USD", MPA_ACCOUNT, billing_period)

    account_usage = result.usage_by_account.get("111111111111")
    assert account_usage is not None
    assert all(
        metric.invoice_entity == "Amazon Web Services, Inc." for metric in account_usage.metrics
    )


def test_run_maps_spp_discount_record_type(generator, mock_aws_client, billing_period):
    rows = [
        {
            "line_item_usage_account_id": "222222222222",
            "line_item_product_code": "AmazonEC2",
            "line_item_line_item_type": "SppDiscount",
            "line_item_unblended_cost": -5.0,
            "bill_invoicing_entity": "Amazon Web Services, Inc.",
            "bill_invoice_id": None,
            "bill_billing_entity": "AWS",
        },
    ]
    key = f"{S3_PREFIX}/data/BILLING_PERIOD%3D2026-03/report.snappy.parquet"
    mock_aws_client.list_s3_objects.return_value = [key]
    mock_aws_client.download_s3_object.return_value = _make_parquet_bytes(rows)

    result = generator.run("USD", MPA_ACCOUNT, billing_period)

    account_usage = result.usage_by_account.get("222222222222")
    assert account_usage is not None
    assert (
        account_usage.metrics[0].record_type == AWSRecordTypeEnum.SOLUTION_PROVIDER_PROGRAM_DISCOUNT
    )
    assert account_usage.metrics[0].amount == Decimal("-5.0")


def test_run_maps_marketplace_billing_entity(generator, mock_aws_client, billing_period):
    rows = [
        {
            "line_item_usage_account_id": "333333333333",
            "line_item_product_code": "MarketplaceProduct",
            "line_item_line_item_type": "Usage",
            "line_item_unblended_cost": 20.0,
            "bill_invoicing_entity": "AWS Marketplace",
            "bill_invoice_id": None,
            "bill_billing_entity": "AWS Marketplace",
        },
    ]
    key = f"{S3_PREFIX}/data/BILLING_PERIOD%3D2026-03/report.snappy.parquet"
    mock_aws_client.list_s3_objects.return_value = [key]
    mock_aws_client.download_s3_object.return_value = _make_parquet_bytes(rows)

    result = generator.run("USD", MPA_ACCOUNT, billing_period)

    account_usage = result.usage_by_account.get("333333333333")
    assert account_usage is not None
    assert account_usage.metrics[0].record_type == "MARKETPLACE"


def test_run_skips_zero_amount_rows(generator, mock_aws_client, billing_period):
    rows = [
        {
            "line_item_usage_account_id": "444444444444",
            "line_item_product_code": "AWSConfig",
            "line_item_line_item_type": "Usage",
            "line_item_unblended_cost": 0,
            "bill_invoicing_entity": "Amazon Web Services, Inc.",
            "bill_invoice_id": None,
            "bill_billing_entity": "AWS",
        },
    ]
    key = f"{S3_PREFIX}/data/BILLING_PERIOD%3D2026-03/report.snappy.parquet"
    mock_aws_client.list_s3_objects.return_value = [key]
    mock_aws_client.download_s3_object.return_value = _make_parquet_bytes(rows)

    result = generator.run("USD", MPA_ACCOUNT, billing_period)

    assert result.usage_by_account == {}


def test_run_concatenates_multiple_parquet_files(generator, mock_aws_client, billing_period):
    rows_file1 = [
        {
            "line_item_usage_account_id": "555555555555",
            "line_item_product_code": "AmazonS3",
            "line_item_line_item_type": "Usage",
            "line_item_unblended_cost": 10.0,
            "bill_invoicing_entity": "Amazon Web Services, Inc.",
            "bill_invoice_id": None,
            "bill_billing_entity": "AWS",
        },
    ]
    rows_file2 = [
        {
            "line_item_usage_account_id": "555555555555",
            "line_item_product_code": "AmazonS3",
            "line_item_line_item_type": "Usage",
            "line_item_unblended_cost": 15.0,
            "bill_invoicing_entity": "Amazon Web Services, Inc.",
            "bill_invoice_id": None,
            "bill_billing_entity": "AWS",
        },
    ]
    key1 = f"{S3_PREFIX}/data/BILLING_PERIOD%3D2026-03/report-00001.snappy.parquet"
    key2 = f"{S3_PREFIX}/data/BILLING_PERIOD%3D2026-03/report-00002.snappy.parquet"
    mock_aws_client.list_s3_objects.return_value = [key1, key2]
    mock_aws_client.download_s3_object.side_effect = [
        _make_parquet_bytes(rows_file1),
        _make_parquet_bytes(rows_file2),
    ]

    result = generator.run("USD", MPA_ACCOUNT, billing_period)

    account_usage = result.usage_by_account.get("555555555555")
    assert account_usage is not None
    assert len(account_usage.metrics) == 2
    assert account_usage.metrics[0].amount == Decimal("10.0")
    assert account_usage.metrics[1].amount == Decimal("15.0")
