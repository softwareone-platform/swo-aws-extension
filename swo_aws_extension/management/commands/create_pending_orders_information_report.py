import datetime as dt

from mpt_extension_sdk.core.utils import setup_client

from swo_aws_extension.config import get_config
from swo_aws_extension.flows.jobs.pending_orders_information_report_creator import (
    PENDING_ORDERS_INFORMATION_REPORT_HEADERS,
    PendingOrdersInformationReportCreator,
)
from swo_aws_extension.management.commands_helpers import StyledPrintCommand
from swo_aws_extension.swo.confluence_client import ConfluenceClient
from swo_aws_extension.swo.excel_report_builder import ExcelReportBuilder


class Command(StyledPrintCommand):
    """Pending orders information report creator command."""

    help = "Create pending orders information report."

    def handle(self, *_args, **_options):  # noqa: WPS110, WPS210
        """Run command."""
        self.info("Starting creation of pending orders information report...")

        today = dt.datetime.now(tz=dt.UTC).strftime("%d-%m-%Y")
        filename = f"orders-{today}.xlsx"

        mpt_client = setup_client()
        config = get_config()

        report_creator = PendingOrdersInformationReportCreator(mpt_client)
        excel_builder = ExcelReportBuilder(
            list(PENDING_ORDERS_INFORMATION_REPORT_HEADERS), sheet_name="Pending Orders"
        )
        confluence_client = ConfluenceClient(config)

        confluence_page_id = config.pending_orders_information_report_page_id

        report_rows = report_creator.create()
        excel_bytes = excel_builder.build_from_rows(report_rows)
        attachment_comment = f"Total orders {len(report_rows)}"

        is_report_uploaded = confluence_client.attach_content(
            page_id=confluence_page_id,
            filename=filename,
            file_content=excel_bytes,
            comment=attachment_comment,
        )

        if not is_report_uploaded:
            self.error("Failed to upload pending orders information report to Confluence")
