from swo_aws_extension.constants import DEC_ZERO, AWSRecordTypeEnum
from swo_aws_extension.flows.jobs.billing_journal.models.journal_line import (
    InvoiceDetails,
    JournalDetails,
    JournalLine,
)
from swo_aws_extension.flows.jobs.billing_journal.models.usage import AccountUsage
from swo_aws_extension.logger import get_logger

ITEM_SKU = "AWS Usage"
logger = get_logger(__name__)

BILLABLE_RECORD_TYPES = (
    AWSRecordTypeEnum.USAGE,
    AWSRecordTypeEnum.SUPPORT,
    AWSRecordTypeEnum.RECURRING,
    AWSRecordTypeEnum.SAVING_PLAN_RECURRING_FEE,
    "MARKETPLACE",
)


class JournalLineGenerator:
    """Generates journal lines from account usage data."""

    def generate(
        self,
        account_id: str,
        account_usage: AccountUsage,
        journal_details: JournalDetails,
    ) -> list[JournalLine]:
        """Generate journal lines for billable metrics in account usage.

        Args:
            account_id: The AWS account ID.
            account_usage: The account usage data containing service metrics.
            journal_details: Journal metadata details.

        Returns:
            List of JournalLine objects for billable record types.
        """
        logger.info("Generating journal lines for account %s: %s", account_id, account_usage)

        return [
            self._metric_to_journal_line(metric, account_id, journal_details)
            for metric in account_usage.metrics
            if metric.amount != DEC_ZERO and metric.record_type in BILLABLE_RECORD_TYPES
        ]

    def _metric_to_journal_line(
        self,
        metric,
        account_id: str,
        journal_details: JournalDetails,
    ) -> JournalLine:
        invoice_details = InvoiceDetails(
            item_sku=ITEM_SKU,
            service_name=metric.service_name,
            amount=metric.amount,
            account_id=account_id,
            invoice_entity=metric.invoice_entity or "",
            invoice_id=metric.invoice_id or "invoice_id",
        )
        return JournalLine.build(ITEM_SKU, journal_details, invoice_details)
