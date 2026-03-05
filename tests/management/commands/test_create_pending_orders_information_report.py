from io import StringIO

from django.core.management import call_command
from freezegun import freeze_time
from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.flows.jobs.pending_orders_information_report_creator import (
    PENDING_ORDERS_INFORMATION_REPORT_HEADERS,
    PendingOrdersInformationReportCreator,
)
from swo_aws_extension.swo.confluence_client import ConfluenceClient
from swo_aws_extension.swo.excel_report_builder import ExcelReportBuilder


@freeze_time("2026-03-09 01:10:10")
def test_create_pending_orders_information_report(mocker, config):
    mock_mpt_client = mocker.MagicMock(spec=MPTClient)
    mock_report_creator = mocker.MagicMock(spec=PendingOrdersInformationReportCreator)
    mock_excel_builder = mocker.MagicMock(spec=ExcelReportBuilder)
    mock_confluence_client = mocker.MagicMock(spec=ConfluenceClient)
    mock_confluence_client.attach_content.return_value = True
    report_rows = [["row1_col1", "row1_col2"], ["row2_col1", "row2_col2"]]
    mock_report_creator.create.return_value = report_rows
    mocked_setup_client = mocker.patch(
        "swo_aws_extension.management.commands.create_pending_orders_information_report.setup_client",
        autospec=True,
        return_value=mock_mpt_client,
    )
    mocker.patch(
        "swo_aws_extension.management.commands.create_pending_orders_information_report.get_config",
        autospec=True,
        return_value=config,
    )
    mocked_report_creator_class = mocker.patch(
        "swo_aws_extension.management.commands.create_pending_orders_information_report.PendingOrdersInformationReportCreator",
        autospec=True,
        return_value=mock_report_creator,
    )
    mocked_excel_builder_class = mocker.patch(
        "swo_aws_extension.management.commands.create_pending_orders_information_report.ExcelReportBuilder",
        autospec=True,
        return_value=mock_excel_builder,
    )
    mocked_confluence_client_class = mocker.patch(
        "swo_aws_extension.management.commands.create_pending_orders_information_report.ConfluenceClient",
        autospec=True,
        return_value=mock_confluence_client,
    )
    filename = "orders-09-03-2026.xlsx"
    comment = f"Total orders {len(report_rows)}"

    call_command("create_pending_orders_information_report")  # act

    mocked_setup_client.assert_called_once()
    mocked_report_creator_class.assert_called_once_with(mock_mpt_client)
    mocked_excel_builder_class.assert_called_once_with(
        list(PENDING_ORDERS_INFORMATION_REPORT_HEADERS), sheet_name="Pending Orders"
    )
    mocked_confluence_client_class.assert_called_once_with(config)
    mock_report_creator.create.assert_called_once()
    mock_excel_builder.build_from_rows.assert_called_once_with(report_rows)
    mock_confluence_client.attach_content.assert_called_once_with(
        page_id=config.pending_orders_information_report_page_id,
        filename=filename,
        file_content=mock_excel_builder.build_from_rows.return_value,
        comment=comment,
    )


@freeze_time("2026-03-09 00:00:00")
def test_create_pending_orders_information_report_upload_failed(mocker, config):
    mock_mpt_client = mocker.MagicMock(spec=MPTClient)
    mock_report_creator = mocker.MagicMock(spec=PendingOrdersInformationReportCreator)
    mock_excel_builder = mocker.MagicMock(spec=ExcelReportBuilder)
    mock_confluence_client = mocker.MagicMock(spec=ConfluenceClient)
    mock_confluence_client.attach_content.return_value = False
    mock_report_creator.create.return_value = []
    mocker.patch(
        "swo_aws_extension.management.commands.create_pending_orders_information_report.setup_client",
        autospec=True,
        return_value=mock_mpt_client,
    )
    mocker.patch(
        "swo_aws_extension.management.commands.create_pending_orders_information_report.get_config",
        autospec=True,
        return_value=config,
    )
    mocker.patch(
        "swo_aws_extension.management.commands.create_pending_orders_information_report.PendingOrdersInformationReportCreator",
        autospec=True,
        return_value=mock_report_creator,
    )
    mocker.patch(
        "swo_aws_extension.management.commands.create_pending_orders_information_report.ExcelReportBuilder",
        autospec=True,
        return_value=mock_excel_builder,
    )
    mocker.patch(
        "swo_aws_extension.management.commands.create_pending_orders_information_report.ConfluenceClient",
        autospec=True,
        return_value=mock_confluence_client,
    )
    stderr = StringIO()
    expected_error_message = "Failed to upload pending orders information report to Confluence"

    call_command("create_pending_orders_information_report", stderr=stderr)  # act

    mock_confluence_client.attach_content.assert_called_once()
    assert expected_error_message in stderr.getvalue()
