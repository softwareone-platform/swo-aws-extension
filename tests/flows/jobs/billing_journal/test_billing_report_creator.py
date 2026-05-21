from decimal import Decimal

import pytest

from swo_aws_extension.config import Config
from swo_aws_extension.flows.jobs.billing_journal.billing_report_creator import BillingReportCreator
from swo_aws_extension.flows.jobs.billing_journal.models.journal_result import BillingReportRow
from swo_aws_extension.swo.notifications.teams import TeamsNotificationManager

MODULE = "swo_aws_extension.flows.jobs.billing_journal.billing_report_creator"


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


def test_create_and_notify_teams_converts_decimals_to_string(
    mock_config, mock_notifier, mock_blob_uploader_cls, mock_excel_builder_cls, sample_row
):
    mock_excel_builder = mock_excel_builder_cls.return_value
    mock_excel_builder.build_multi_sheet.return_value = b"excel_bytes"
    mock_blob_uploader_cls.return_value.upload_and_get_sas_url.return_value = "https://url"
    creator = BillingReportCreator(mock_config, mock_notifier)

    creator.create_and_notify_teams("2024-01", [sample_row])  # act

    call_args = mock_excel_builder.build_multi_sheet.call_args[0][0]
    sheet1_name, _, sheet1_rows = call_args[0]
    assert sheet1_name == "Billing Report"
    expected_row = [
        "AUTH-1",
        "PMA-1",
        "AGR-1",
        "MPA-1",
        "EC2",
        "10.5",
        "11.5",
        "USD",
        "INV-1",
        "INV-E1",
        "1.2",
        "-1.0",
        "0,0870 (8.70%)",
    ]
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
    assert sheet2_name == "By Linked Account"
    assert "Linked Account" in sheet2_headers
    assert sheet2_rows[0][4] == "ACC-001"
