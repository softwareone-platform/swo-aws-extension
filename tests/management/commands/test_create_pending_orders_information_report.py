from django.core.management import call_command
from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.flows.jobs.pending_orders_information_report_creator import (
    PENDING_ORDERS_INFORMATION_REPORT_HEADERS,
    PendingOrdersInformationReportCreator,
)


def test_create_pending_orders_information_report(mocker, config):
    mock_mpt_client = mocker.MagicMock(spec=MPTClient)
    mock_report_creator = mocker.MagicMock(spec=PendingOrdersInformationReportCreator)
    mock_excel_builder = mocker.MagicMock()
    mocked_setup_client = mocker.patch(
        "swo_aws_extension.management.commands.create_pending_orders_information_report.setup_client",
        autospec=True,
        return_value=mock_mpt_client,
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

    call_command("create_pending_orders_information_report")  # act

    mocked_setup_client.assert_called_once()
    mocked_report_creator_class.assert_called_once_with(mock_mpt_client, config)
    mocked_excel_builder_class.assert_called_once_with(
        list(PENDING_ORDERS_INFORMATION_REPORT_HEADERS), sheet_name="Pending Orders"
    )
    mock_report_creator.create.assert_called_once()
    mock_excel_builder.build_from_rows.assert_called_once_with(
        mock_report_creator.create.return_value
    )
    mock_excel_builder.save.assert_called_once()
