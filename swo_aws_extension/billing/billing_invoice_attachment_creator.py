from io import BytesIO

import requests

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.billing.models.journal_result import InvoiceAttachmentResult
from swo_aws_extension.logger import get_logger
from swo_aws_extension.swo.mpt.billing.billing_client import BillingClient
from swo_aws_extension.swo.mpt.billing.models.hints import JournalAttachment

logger = get_logger(__name__)


class BillingInvoiceAttachmentCreator:
    """Creates AWS invoice attachments for a billing journal."""

    def __init__(self, aws_client: AWSClient, billing_api_client: BillingClient) -> None:
        self._aws_client = aws_client
        self._billing_api_client = billing_api_client

    def create_for_journal(
        self,
        journal_id: str,
        invoice_ids: set[str],
    ) -> InvoiceAttachmentResult:
        """Retrieve and attach AWS invoices to a journal."""
        result = InvoiceAttachmentResult()
        for invoice_id in sorted(invoice_ids):
            try:
                self._create_attachment(journal_id, invoice_id)
            except (AWSError, requests.RequestException):
                logger.exception(
                    "Failed to attach AWS invoice %s to journal %s",
                    invoice_id,
                    journal_id,
                )
                result.failed_invoice_ids.add(invoice_id)
                continue
            result.uploaded_invoice_ids.add(invoice_id)
        return result

    def _create_attachment(self, journal_id: str, invoice_id: str) -> None:
        invoice_file = BytesIO(self._aws_client.download_invoice_pdf(invoice_id))
        filename = f"AWS-Invoice-{invoice_id}.pdf"
        attachment = JournalAttachment(
            name=filename,
            description=f"AWS invoice {invoice_id}",
        )
        self._billing_api_client.journal.attachments(journal_id).upload(
            filename=filename,
            mimetype="application/pdf",
            file=invoice_file,
            attachment=attachment,
        )
        logger.info("Uploaded AWS invoice %s to journal %s", invoice_id, journal_id)
