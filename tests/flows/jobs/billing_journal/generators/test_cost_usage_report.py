from decimal import Decimal

import pytest

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.constants import AWS_MARKETPLACE, AWSRecordTypeEnum
from swo_aws_extension.flows.jobs.billing_journal.generators.cost_usage_report import (
    CostUsageReportGenerator,
    S3ParquetReportFetcher,
)
from swo_aws_extension.flows.jobs.billing_journal.models.billing_period import BillingPeriod
from swo_aws_extension.flows.jobs.billing_journal.models.usage import OrganizationUsageResult

_BILLING_VIEW_ARN = "arn:aws:billing::123456789:billingview/my-view"
_EXPECTED_S3_PREFIX = (
    "cur-PMA-1/arn:aws:billing::123456789:billingview/my-view"
    "/PMA-1-MPA-1-my-view/data/BILLING_PERIOD=2026-03"
)


def _build_pyarrow_table(rows):
    """Build a PyArrow table from row dictionaries."""
    pyarrow = pytest.importorskip("pyarrow")
    column_names = {
        "line_item_usage_account_id",
        "line_item_product_code",
        "line_item_line_item_type",
        "line_item_unblended_cost",
        "bill_invoicing_entity",
        "bill_invoice_id",
        "bill_billing_entity",
    }
    columns = {
        column_name: [row.get(column_name) for row in rows] for column_name in sorted(column_names)
    }
    return pyarrow.table(columns)


def _build_parquet_bytes(rows):
    """Build parquet-encoded bytes from row dictionaries."""
    pyarrow = pytest.importorskip("pyarrow")
    parquet = pytest.importorskip("pyarrow.parquet")
    sink = pyarrow.BufferOutputStream()
    parquet.write_table(_build_pyarrow_table(rows), sink)
    return sink.getvalue().to_pybytes()


@pytest.fixture
def mock_aws_client(mocker):
    client = mocker.MagicMock(spec=AWSClient)
    client.account_id = "PMA-1"
    client.get_billing_views_by_account_id.return_value = []
    return client


@pytest.fixture
def billing_period():
    return BillingPeriod(start_date="2026-03-01", end_date="2026-04-01")


@pytest.fixture
def fetcher(mock_aws_client):
    return S3ParquetReportFetcher(mock_aws_client, "billing-bucket", "cur-prefix")


@pytest.fixture
def generator(mock_aws_client):
    return CostUsageReportGenerator(mock_aws_client)


@pytest.fixture
def valid_rows():
    return [
        {
            "line_item_usage_account_id": "ACT-1",
            "line_item_product_code": "AmazonEC2",
            "line_item_line_item_type": "Usage",
            "line_item_unblended_cost": "10.25",
            "bill_invoicing_entity": "Amazon Web Services, Inc.",
            "bill_invoice_id": "INV-001",
            "bill_billing_entity": "AWS",
        },
        {
            "line_item_usage_account_id": "ACT-1",
            "line_item_product_code": "AWSMarketplaceService",
            "line_item_line_item_type": "Refund",
            "line_item_unblended_cost": "4.50",
            "bill_invoicing_entity": "Marketplace Entity",
            "bill_invoice_id": "INV-002",
            "bill_billing_entity": AWS_MARKETPLACE,
        },
        {
            "line_item_usage_account_id": "ACT-2",
            "line_item_product_code": "AmazonRDS",
            "line_item_line_item_type": "CustomType",
            "line_item_unblended_cost": "3",
            "bill_invoicing_entity": None,
            "bill_invoice_id": None,
            "bill_billing_entity": "AWS",
        },
        {
            "line_item_usage_account_id": "ACT-2",
            "line_item_product_code": "AmazonSupport",
            "line_item_line_item_type": "SppDiscount",
            "line_item_unblended_cost": "1.25",
            "bill_invoicing_entity": "Amazon Web Services EMEA SARL",
            "bill_invoice_id": "INV-007",
            "bill_billing_entity": "AWS",
        },
    ]


@pytest.fixture
def skipped_rows():
    return [
        {
            "line_item_usage_account_id": "ACT-1",
            "line_item_product_code": "AmazonS3",
            "line_item_line_item_type": "Usage",
            "line_item_unblended_cost": "0",
            "bill_invoicing_entity": "Entity",
            "bill_invoice_id": "INV-003",
            "bill_billing_entity": "AWS",
        },
        {
            "line_item_usage_account_id": "",
            "line_item_product_code": "AmazonVPC",
            "line_item_line_item_type": "Usage",
            "line_item_unblended_cost": "1.00",
            "bill_invoicing_entity": "Entity",
            "bill_invoice_id": "INV-004",
            "bill_billing_entity": "AWS",
        },
        {
            "line_item_usage_account_id": "ACT-3",
            "line_item_product_code": "",
            "line_item_line_item_type": "Usage",
            "line_item_unblended_cost": "1.00",
            "bill_invoicing_entity": "Entity",
            "bill_invoice_id": "INV-005",
            "bill_billing_entity": "AWS",
        },
        {
            "line_item_usage_account_id": "ACT-3",
            "line_item_product_code": "AmazonCloudWatch",
            "line_item_line_item_type": "Usage",
            "line_item_unblended_cost": None,
            "bill_invoicing_entity": "Entity",
            "bill_invoice_id": "INV-006",
            "bill_billing_entity": "AWS",
        },
    ]


def test_list_billing_period_keys_returns_only_parquet_files(fetcher, mock_aws_client):
    mock_aws_client.list_s3_objects.return_value = [
        "cur-prefix/file-1.parquet",
        "cur-prefix/file-2.csv",
        "cur-prefix/file-3.parquet",
    ]

    result = fetcher.list_billing_period_keys()

    assert result == [
        "cur-prefix/file-1.parquet",
        "cur-prefix/file-3.parquet",
    ]
    mock_aws_client.list_s3_objects.assert_called_once_with(
        "billing-bucket",
        "cur-prefix",
    )


def test_download_parquet_table_reads_bytes(fetcher, mock_aws_client):
    mock_aws_client.download_s3_object.return_value = _build_parquet_bytes([
        {
            "line_item_usage_account_id": "ACT-1",
            "line_item_product_code": "AmazonEC2",
            "line_item_line_item_type": "Usage",
            "line_item_unblended_cost": "10.25",
            "bill_invoicing_entity": "Amazon Web Services, Inc.",
            "bill_invoice_id": "INV-001",
            "bill_billing_entity": "AWS",
        }
    ])

    result = fetcher.download_parquet_table("cur-prefix/BILLING_PERIOD%3D2026-03/file-1.parquet")

    assert result.num_rows == 1
    assert result.column_names == [
        "bill_billing_entity",
        "bill_invoice_id",
        "bill_invoicing_entity",
        "line_item_line_item_type",
        "line_item_product_code",
        "line_item_unblended_cost",
        "line_item_usage_account_id",
    ]


def test_s3_parquet_path_returns_expected_prefix(generator, mock_aws_client, billing_period):
    mock_aws_client.get_billing_views_by_account_id.return_value = [{"arn": _BILLING_VIEW_ARN}]

    result = generator.s3_parquet_path("MPA-1", billing_period)

    assert result == _EXPECTED_S3_PREFIX


def test_s3_parquet_path_returns_empty_string_when_billing_view_is_missing(
    generator,
    billing_period,
):
    result = generator.s3_parquet_path("MPA-1", billing_period)

    assert not result


def test_run_returns_empty_result_when_no_billing_view(generator, mock_aws_client, billing_period):
    result = generator.run("USD", "MPA-1", billing_period)

    assert isinstance(result, OrganizationUsageResult)
    assert not result.reports.organization_data
    assert not result.reports.accounts_data
    assert not result.usage_by_account
    mock_aws_client.list_s3_objects.assert_not_called()


def test_run_returns_empty_result_when_no_parquet_files(
    generator, mock_aws_client, billing_period
):
    mock_aws_client.get_billing_views_by_account_id.return_value = [
        {"arn": _BILLING_VIEW_ARN}
    ]
    mock_aws_client.list_s3_objects.return_value = []

    result = generator.run("USD", "MPA-1", billing_period)

    assert isinstance(result, OrganizationUsageResult)
    assert not result.reports.organization_data
    assert not result.reports.accounts_data
    assert not result.usage_by_account
    mock_aws_client.list_s3_objects.assert_called_once_with(
        "mpt-billing-PMA-1", _EXPECTED_S3_PREFIX
    )


def test_run_processes_standard_usage_metrics(  # noqa: WPS218
    generator,
    mocker,
    mock_aws_client,
    billing_period,
    valid_rows,
):
    mock_aws_client.get_billing_views_by_account_id.return_value = [
        {"arn": _BILLING_VIEW_ARN}
    ]
    mock_aws_client.list_s3_objects.return_value = [
        f"{_EXPECTED_S3_PREFIX}/file-1.parquet",
    ]
    mocker.patch.object(
        S3ParquetReportFetcher,
        "download_parquet_table",
        autospec=True,
        return_value=_build_pyarrow_table(valid_rows[:1]),
    )

    result = generator.run("USD", "MPA-1", billing_period)

    assert "ACT-1" in result.usage_by_account
    metrics = result.usage_by_account["ACT-1"].metrics
    assert len(metrics) == 1
    metric = metrics[0]
    assert metric.service_name == "AmazonEC2"
    assert metric.record_type == AWSRecordTypeEnum.USAGE
    assert metric.amount == Decimal("10.25")
    assert metric.invoice_entity == "Amazon Web Services, Inc."
    assert metric.invoice_id == "INV-001"


def test_run_processes_marketplace_metrics(
    generator,
    mocker,
    mock_aws_client,
    billing_period,
    valid_rows,
):
    mock_aws_client.get_billing_views_by_account_id.return_value = [
        {"arn": _BILLING_VIEW_ARN}
    ]
    mock_aws_client.list_s3_objects.return_value = [
        f"{_EXPECTED_S3_PREFIX}/file-1.parquet",
    ]
    mocker.patch.object(
        S3ParquetReportFetcher,
        "download_parquet_table",
        autospec=True,
        return_value=_build_pyarrow_table(valid_rows[1:2]),
    )

    result = generator.run("USD", "MPA-1", billing_period)

    assert "ACT-1" in result.usage_by_account
    metrics = result.usage_by_account["ACT-1"].metrics
    assert len(metrics) == 1
    assert metrics[0].service_name == "AWSMarketplaceService"
    assert metrics[0].record_type == "MARKETPLACE"
    assert metrics[0].amount == Decimal("4.50")


def test_run_skips_zero_cost_and_invalid_rows(
    generator,
    mocker,
    mock_aws_client,
    billing_period,
    skipped_rows,
):
    mock_aws_client.get_billing_views_by_account_id.return_value = [
        {"arn": _BILLING_VIEW_ARN}
    ]
    mock_aws_client.list_s3_objects.return_value = [
        f"{_EXPECTED_S3_PREFIX}/file-1.parquet",
    ]
    mocker.patch.object(
        S3ParquetReportFetcher,
        "download_parquet_table",
        autospec=True,
        return_value=_build_pyarrow_table(skipped_rows),
    )

    result = generator.run("USD", "MPA-1", billing_period)

    assert not result.usage_by_account


def test_run_merges_multiple_parquet_files(
    generator,
    mocker,
    mock_aws_client,
    billing_period,
    valid_rows,
):
    mock_aws_client.get_billing_views_by_account_id.return_value = [
        {"arn": _BILLING_VIEW_ARN}
    ]
    mock_aws_client.list_s3_objects.return_value = [
        f"{_EXPECTED_S3_PREFIX}/file-1.parquet",
        f"{_EXPECTED_S3_PREFIX}/file-2.parquet",
    ]
    download_parquet_table = mocker.patch.object(
        S3ParquetReportFetcher,
        "download_parquet_table",
        autospec=True,
        side_effect=[
            _build_pyarrow_table(valid_rows[:2]),
            _build_pyarrow_table(valid_rows[2:]),
        ],
    )

    result = generator.run("USD", "MPA-1", billing_period)

    assert set(result.usage_by_account) == {"ACT-1", "ACT-2"}
    assert len(result.usage_by_account["ACT-1"].metrics) == 2
    assert len(result.usage_by_account["ACT-2"].metrics) == 2
    download_parquet_table.assert_has_calls([
        mocker.call(mocker.ANY, f"{_EXPECTED_S3_PREFIX}/file-1.parquet"),
        mocker.call(mocker.ANY, f"{_EXPECTED_S3_PREFIX}/file-2.parquet"),
    ])


def test_run_preserves_custom_record_types_and_optional_fields(  # noqa: WPS218
    generator,
    mocker,
    mock_aws_client,
    billing_period,
    valid_rows,
):
    mock_aws_client.get_billing_views_by_account_id.return_value = [
        {"arn": _BILLING_VIEW_ARN}
    ]
    mock_aws_client.list_s3_objects.return_value = [
        f"{_EXPECTED_S3_PREFIX}/file-1.parquet",
    ]
    mocker.patch.object(
        S3ParquetReportFetcher,
        "download_parquet_table",
        autospec=True,
        return_value=_build_pyarrow_table(valid_rows[2:4]),
    )

    result = generator.run("USD", "MPA-1", billing_period)

    act_two = result.usage_by_account["ACT-2"]
    custom_metric = next(metric for metric in act_two.metrics if metric.service_name == "AmazonRDS")
    spp_metric = next(
        metric for metric in act_two.metrics if metric.service_name == "AmazonSupport"
    )
    assert custom_metric.record_type == "CustomType"
    assert not custom_metric.invoice_entity
    assert not custom_metric.invoice_id
    assert spp_metric.record_type == AWSRecordTypeEnum.SOLUTION_PROVIDER_PROGRAM_DISCOUNT
    assert spp_metric.invoice_entity == "Amazon Web Services EMEA SARL"
    assert spp_metric.invoice_id == "INV-007"
