from swo_aws_extension.config import Config
from swo_aws_extension.flows.jobs.billing_journal.models.journal_result import BillingReportRow
from swo_aws_extension.logger import get_logger
from swo_aws_extension.swo.azure_blob_uploader import AzureBlobUploader
from swo_aws_extension.swo.excel_report_builder import ExcelReportBuilder
from swo_aws_extension.swo.notifications.teams import Button, TeamsNotificationManager

logger = get_logger(__name__)

BILLING_REPORT_HEADERS = (
    "Authorization ID",
    "PMA",
    "Agreement ID",
    "MPA",
    "Service Name",
    "Amount",
    "Currency",
    "Invoice ID",
    "Invoice Entity",
    "Exchange Rate",
    "SPP Discount",
)


class BillingReportCreator:
    """Creates a unified Excel billing report."""

    def __init__(self, config: Config, notifier: TeamsNotificationManager) -> None:
        self._config = config
        self._notifier = notifier
        self._excel_builder = ExcelReportBuilder(list(BILLING_REPORT_HEADERS))
        self._blob_uploader = AzureBlobUploader(
            connection_string=self._config.azure_storage_connection_string,
            container_name=self._config.azure_storage_container,
            sas_expiry_days=self._config.azure_storage_sas_expiry_days,
        )

    def create_and_notify_teams(
        self, billing_period_str: str, report_rows: list[BillingReportRow]
    ) -> None:
        """Create the report, upload to Azure, and notify teams."""
        if not report_rows:
            logger.info("No billing report rows. Skipping Excel report creation.")
            return

        logger.info("Creating billing report Excel file...")
        rows_data = self._build_rows_data(report_rows)
        excel_bytes = self._generate_excel(rows_data)
        folder = self._config.report_billing_folder
        blob_name = f"{folder}{billing_period_str}.xlsx"

        try:
            download_url = self._upload(excel_bytes, blob_name)
        except Exception as exc:
            logger.exception("Failed to upload billing report to Azure Blob Storage.")
            self._notifier.send_error(
                "Billing Report Failure",
                f"Failed to upload the monthly billing report to Azure: {exc}",
            )
            return

        self._notifier.send_success(
            "AWS Monthly Billing Report",
            (
                f"The billing report for **{billing_period_str}** has been generated "
                f"containing **{len(rows_data)}** rows."
            ),
            button=Button(label="Download report", url=download_url),
        )
        logger.info("Billing report uploaded and Teams notification sent.")

    def _generate_excel(self, rows_data: list[list[str]]) -> bytes:
        return self._excel_builder.build_from_rows(rows_data)

    def _upload(self, excel_bytes: bytes, blob_name: str) -> str:
        return self._blob_uploader.upload_and_get_sas_url(excel_bytes, blob_name)

    def _build_rows_data(self, report_rows: list[BillingReportRow]) -> list[list[str]]:
        return [
            [
                row.authorization_id,
                row.pma,
                row.agreement_id,
                row.mpa,
                row.service_name,
                str(row.amount),
                row.currency,
                row.invoice_id,
                row.invoice_entity,
                str(row.exchange_rate),
                str(row.spp_discount),
            ]
            for row in report_rows
        ]
