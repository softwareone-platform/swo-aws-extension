import datetime as dt

from mpt_extension_sdk.core.utils import setup_client

from swo_aws_extension.config import get_config
from swo_aws_extension.flows.jobs.pending_orders_information_report_creator import (
    PENDING_ORDERS_INFORMATION_REPORT_HEADERS,
    PendingOrdersInformationReportCreator,
)
from swo_aws_extension.management.commands_helpers import StyledPrintCommand
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

        report_creator = PendingOrdersInformationReportCreator(mpt_client, get_config())
        excel_builder = ExcelReportBuilder(
            list(PENDING_ORDERS_INFORMATION_REPORT_HEADERS), sheet_name="Pending Orders"
        )

        report_rows = report_creator.create()
        excel_bytes = excel_builder.build_from_rows(report_rows)
        excel_builder.save(filename, excel_bytes)

        self.info(f"Pending orders information report created at {filename}")
