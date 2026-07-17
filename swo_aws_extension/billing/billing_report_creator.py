from swo_aws_extension.billing.models.journal_result import (
    BillingReportRow,
    OrganizationSppSummaryRow,
)
from swo_aws_extension.config import Config
from swo_aws_extension.logger import get_logger
from swo_aws_extension.swo.azure_blob_uploader import AzureBlobUploader
from swo_aws_extension.swo.excel_report_builder import CellValue, ExcelReportBuilder, Percent
from swo_aws_extension.swo.notifications.teams import Button, TeamsNotificationManager

logger = get_logger(__name__)

HEADER_AUTHORIZATION_ID = "Authorization ID"
HEADER_AGREEMENT_ID = "Agreement ID"
HEADER_EXCHANGE_RATE = "Exchange Rate"
HEADER_SPP_DISCOUNT = "SPP Discount"
HEADER_SPP_DISCOUNT_PCT = "SPP Discount %"


BILLING_REPORT_HEADERS = (
    HEADER_AUTHORIZATION_ID,
    "PMA",
    HEADER_AGREEMENT_ID,
    "MPA",
    "Service Name",
    "PP",
    "SP",
    "Currency",
    "Invoice ID",
    "Invoice Entity",
    HEADER_EXCHANGE_RATE,
    HEADER_SPP_DISCOUNT,
    HEADER_SPP_DISCOUNT_PCT,
)

BILLING_REPORT_BY_ACCOUNT_HEADERS = (
    HEADER_AUTHORIZATION_ID,
    "PMA",
    HEADER_AGREEMENT_ID,
    "MPA",
    "Linked Account",
    "Service Name",
    "PP",
    "SP",
    "Currency",
    "Invoice ID",
    "Invoice Entity",
    HEADER_EXCHANGE_RATE,
    HEADER_SPP_DISCOUNT,
    HEADER_SPP_DISCOUNT_PCT,
)

SPP_SUMMARY_HEADERS = (
    HEADER_AUTHORIZATION_ID,
    "PMA",
    HEADER_AGREEMENT_ID,
    "MPA",
    "PP",
    "SP",
    "Currency",
    HEADER_EXCHANGE_RATE,
    HEADER_SPP_DISCOUNT,
    HEADER_SPP_DISCOUNT_PCT,
    "Markup",
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
        self,
        billing_period_str: str,
        report_rows: list[BillingReportRow],
        rows_by_account: list[BillingReportRow] | None = None,
        spp_summary_rows: list[OrganizationSppSummaryRow] | None = None,
    ) -> None:
        """Create the report, upload to Azure, and notify teams."""
        if not report_rows:
            logger.info("No billing report rows. Skipping Excel report creation.")
            return

        logger.info("Creating billing report Excel file...")
        rows_data = self._build_rows_data(report_rows)
        excel_bytes = self._generate_excel(
            rows_data,
            self._build_rows_by_account_data(rows_by_account or []),
            self._build_spp_summary_rows_data(spp_summary_rows or []),
        )
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

    def _generate_excel(
        self,
        rows_data: list[list[CellValue]],
        by_account_data: list[list[CellValue]],
        spp_summary_data: list[list[CellValue]],
    ) -> bytes:
        return self._excel_builder.build_multi_sheet([
            ("Billing Report", list(BILLING_REPORT_HEADERS), rows_data),
            ("By Linked Account", list(BILLING_REPORT_BY_ACCOUNT_HEADERS), by_account_data),
            ("SPP Summary", list(SPP_SUMMARY_HEADERS), spp_summary_data),
        ])

    def _upload(self, excel_bytes: bytes, blob_name: str) -> str:
        return self._blob_uploader.upload_and_get_sas_url(excel_bytes, blob_name)

    def _build_rows_data(self, report_rows: list[BillingReportRow]) -> list[list[CellValue]]:
        return [
            [
                row.authorization_id,
                row.pma,
                row.agreement_id,
                row.mpa,
                row.service_name,
                float(row.pp),
                float(row.sp),
                row.currency,
                row.invoice_id,
                row.invoice_entity,
                float(row.exchange_rate),
                float(row.spp_discount),
                Percent(float(row.spp_discount_pct)),
            ]
            for row in report_rows
        ]

    def _build_rows_by_account_data(self, rows: list[BillingReportRow]) -> list[list[CellValue]]:
        return [
            [
                row.authorization_id,
                row.pma,
                row.agreement_id,
                row.mpa,
                row.linked_account,
                row.service_name,
                float(row.pp),
                float(row.sp),
                row.currency,
                row.invoice_id,
                row.invoice_entity,
                float(row.exchange_rate),
                float(row.spp_discount),
                Percent(float(row.spp_discount_pct)),
            ]
            for row in rows
        ]

    def _build_spp_summary_rows_data(
        self, rows: list[OrganizationSppSummaryRow]
    ) -> list[list[CellValue]]:
        return [
            [
                row.authorization_id,
                row.pma,
                row.agreement_id,
                row.mpa,
                float(row.pp),
                float(row.sp),
                row.currency,
                float(row.exchange_rate),
                float(row.spp_discount),
                Percent(float(row.spp_discount_pct)),
                Percent(float(row.markup)),
            ]
            for row in rows
        ]
