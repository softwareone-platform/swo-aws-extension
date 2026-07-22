from decimal import Decimal

import pytest

from swo_aws_extension.billing.billing_report_creator import BillingReportCreator
from swo_aws_extension.billing.models.journal_result import (
    BillingReportRow,
    OrganizationSppSummaryRow,
)
from swo_aws_extension.config import Config
from swo_aws_extension.swo.excel_report_builder import Percent
from swo_aws_extension.swo.notifications.teams import TeamsNotificationManager

MODULE = "swo_aws_extension.billing.billing_report_creator"


@pytest.fixture
def mock_config():
    return Config()


@pytest.fixture
def mock_notifier(mocker):
    return mocker.MagicMock(spec=TeamsNotificationManager)


@pytest.fixture
def mock_blob_uploader_cls(mocker):
    return mocker.patch(f"{MODULE}.AzureBlobUploader", autospec=True)


@pytest.fixture
def mock_excel_builder_cls(mocker):
    return mocker.patch(f"{MODULE}.ExcelReportBuilder", autospec=True)


@pytest.fixture
def sample_row():
    return BillingReportRow(
        authorization_id="AUTH-1",
        pma="PMA-1",
        agreement_id="AGR-1",
        mpa="MPA-1",
        service_name="EC2",
        pp=Decimal("10.5"),
        sp=Decimal("11.5"),
        currency="USD",
        invoice_id="INV-1",
        invoice_entity="INV-E1",
        exchange_rate=Decimal("1.2"),
        spp_discount=Decimal("-1.0"),
        spp_discount_pct=Decimal("1.0") / Decimal("11.5"),
    )


@pytest.fixture
def sample_spp_summary_row():
    return OrganizationSppSummaryRow(
        authorization_id="AUTH-1",
        pma="PMA-1",
        agreement_id="AGR-1",
        mpa="MPA-1",
        pp=Decimal("90.0"),
        sp=Decimal("100.0"),
        currency="USD",
        exchange_rate=Decimal("1.0"),
        spp_discount=Decimal("-10.0"),
        spp_discount_pct=Decimal("1.0") / Decimal("9.0"),
        markup=Decimal("10.0") / Decimal("90.0"),
    )


def test_create_and_notify_teams_skips_empty(
    mock_config, mock_notifier, mock_blob_uploader_cls, mock_excel_builder_cls
):
    creator = BillingReportCreator(mock_config, mock_notifier)

    creator.create_and_notify_teams("2024-01", [])  # act

    mock_excel_builder_cls.return_value.build_multi_sheet.assert_not_called()
    mock_notifier.send_success.assert_not_called()


def test_create_and_notify_teams_success(
    mock_config, mock_notifier, mock_blob_uploader_cls, mock_excel_builder_cls, sample_row
):
    mock_excel_builder = mock_excel_builder_cls.return_value
    mock_excel_builder.build_multi_sheet.return_value = b"excel_bytes"
    mock_blob_uploader = mock_blob_uploader_cls.return_value
    mock_blob_uploader.upload_and_get_sas_url.return_value = "https://azure.blob/report.xlsx"
    creator = BillingReportCreator(mock_config, mock_notifier)

    creator.create_and_notify_teams("2024-01", [sample_row])  # act

    mock_excel_builder.build_multi_sheet.assert_called_once()
    mock_blob_uploader.upload_and_get_sas_url.assert_called_once()
    mock_notifier.send_success.assert_called_once()


def test_create_and_notify_teams_upload_failure(
    mock_config, mock_notifier, mock_blob_uploader_cls, mock_excel_builder_cls, sample_row
):
    mock_excel_builder_cls.return_value.build_multi_sheet.return_value = b"excel_bytes"
    mock_blob_uploader_cls.return_value.upload_and_get_sas_url.side_effect = Exception(
        "Upload failed"
    )
    creator = BillingReportCreator(mock_config, mock_notifier)

    creator.create_and_notify_teams("2024-01", [sample_row])  # act

    mock_notifier.send_success.assert_not_called()
    mock_notifier.send_error.assert_called_once()


def test_create_and_notify_teams_converts_decimals_to_numeric(
    mock_config, mock_notifier, mock_blob_uploader_cls, mock_excel_builder_cls, sample_row
):
    mock_excel_builder = mock_excel_builder_cls.return_value
    mock_excel_builder.build_multi_sheet.return_value = b"excel_bytes"
    mock_blob_uploader_cls.return_value.upload_and_get_sas_url.return_value = "https://url"
    creator = BillingReportCreator(mock_config, mock_notifier)

    creator.create_and_notify_teams("2024-01", [sample_row])  # act

    call_args = mock_excel_builder.build_multi_sheet.call_args[0][0]
    sheet1_name, _, sheet1_rows = call_args[0]
    expected_row = [
        "AUTH-1",
        "PMA-1",
        "AGR-1",
        "MPA-1",
        "EC2",
        10.5,
        11.5,
        "USD",
        "INV-1",
        "INV-E1",
        1.2,
        -1.0,
        Percent(float(sample_row.spp_discount_pct)),
    ]
    assert sheet1_name == "Billing Report"
    assert sheet1_rows == [expected_row]


def test_create_and_notify_teams_builds_by_account_sheet(
    mock_config, mock_notifier, mock_blob_uploader_cls, mock_excel_builder_cls, sample_row
):
    mock_excel_builder = mock_excel_builder_cls.return_value
    mock_excel_builder.build_multi_sheet.return_value = b"excel_bytes"
    mock_blob_uploader_cls.return_value.upload_and_get_sas_url.return_value = "https://url"
    by_account_row = BillingReportRow(
        authorization_id="AUTH-1",
        pma="PMA-1",
        agreement_id="AGR-1",
        mpa="MPA-1",
        service_name="EC2",
        pp=Decimal("10.5"),
        sp=Decimal("11.5"),
        currency="USD",
        invoice_id="INV-1",
        invoice_entity="INV-E1",
        exchange_rate=Decimal("1.2"),
        spp_discount=Decimal("-1.0"),
        spp_discount_pct=Decimal("1.0") / Decimal("11.5"),
        linked_account="ACC-001",
    )
    creator = BillingReportCreator(mock_config, mock_notifier)

    creator.create_and_notify_teams("2024-01", [sample_row], [by_account_row])  # act

    call_args = mock_excel_builder.build_multi_sheet.call_args[0][0]
    sheet2_name, sheet2_headers, sheet2_rows = call_args[1]
    expected_row = [
        "AUTH-1",
        "PMA-1",
        "AGR-1",
        "MPA-1",
        "ACC-001",
        "EC2",
        10.5,
        11.5,
        "USD",
        "INV-1",
        "INV-E1",
        1.2,
        -1.0,
        Percent(float(by_account_row.spp_discount_pct)),
    ]
    assert sheet2_name == "By Linked Account"
    assert "Linked Account" in sheet2_headers
    assert sheet2_rows == [expected_row]


def test_create_and_notify_teams_builds_spp_summary_sheet(
    mock_config,
    mock_notifier,
    mock_blob_uploader_cls,
    mock_excel_builder_cls,
    sample_row,
    sample_spp_summary_row,
):
    mock_excel_builder = mock_excel_builder_cls.return_value
    mock_excel_builder.build_multi_sheet.return_value = b"excel_bytes"
    mock_blob_uploader_cls.return_value.upload_and_get_sas_url.return_value = "https://url"
    creator = BillingReportCreator(mock_config, mock_notifier)

    creator.create_and_notify_teams("2024-01", [sample_row], None, [sample_spp_summary_row])  # act

    call_args = mock_excel_builder.build_multi_sheet.call_args[0][0]
    sheet3_name, sheet3_headers, sheet3_rows = call_args[2]
    assert sheet3_name == "SPP Summary"
    assert list(sheet3_headers) == [
        "Authorization ID",
        "PMA",
        "Agreement ID",
        "MPA",
        "PP",
        "SP",
        "Currency",
        "Exchange Rate",
        "SPP Discount",
        "SPP Discount %",
        "Markup",
    ]
    expected_row = [
        "AUTH-1",
        "PMA-1",
        "AGR-1",
        "MPA-1",
        90.0,
        100.0,
        "USD",
        1.0,
        -10.0,
        Percent(float(sample_spp_summary_row.spp_discount_pct)),
        Percent(float(sample_spp_summary_row.markup)),
    ]
    assert sheet3_rows == [expected_row]
