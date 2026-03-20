from decimal import Decimal

from swo_aws_extension.constants import DEC_ZERO
from swo_aws_extension.flows.jobs.billing_journal.models.context import LineProcessorContext
from swo_aws_extension.flows.jobs.billing_journal.models.invoice import OrganizationInvoice
from swo_aws_extension.flows.jobs.billing_journal.models.journal_line import (
    InvoiceDetails,
    JournalLine,
)
from swo_aws_extension.flows.jobs.billing_journal.models.usage import ServiceMetric

ITEM_SKU = "AWS Usage"


class LineProcessor:
    """Base class for all line processors."""

    def __init__(
        self,
        prefix_name: str = "",
        suffix_name: str = "",
    ) -> None:
        self._prefix_name = prefix_name
        self._suffix_name = suffix_name

    def process(
        self,
        metric: ServiceMetric,
        context: LineProcessorContext,
    ) -> list[JournalLine]:
        """Process a metric and return journal lines.

        Args:
            metric: The service metric to process.
            context: Shared context for the current account.

        Returns:
            List of journal lines (empty if metric should be skipped).
        """
        if metric.amount == DEC_ZERO:
            return []
        return [self._build_line(metric, context)]

    def _build_line(
        self,
        metric: ServiceMetric,
        context: LineProcessorContext,
    ) -> JournalLine:
        service_name = f"{self._prefix_name}{metric.service_name}{self._suffix_name}"
        service_amount = self._resolve_service_amount(metric, context.organization_invoice)
        invoice_details = InvoiceDetails(
            item_sku=ITEM_SKU,
            service_name=service_name,
            amount=service_amount,
            account_id=context.account_id,
            invoice_entity=metric.invoice_entity or "",
            invoice_id=metric.invoice_id or "invoice_id",
        )
        return JournalLine.build(ITEM_SKU, context.journal_details, invoice_details)

    def _resolve_service_amount(
        self,
        metric: ServiceMetric,
        organization_invoice: OrganizationInvoice,
    ) -> Decimal:
        invoice_entity_name = metric.invoice_entity or ""
        invoice_entity = organization_invoice.entities.get(invoice_entity_name)
        if not invoice_entity:
            return metric.amount

        if invoice_entity.payment_currency_code == invoice_entity.base_currency_code:
            return metric.amount
        if invoice_entity.exchange_rate <= DEC_ZERO:
            return metric.amount

        return round(metric.amount * invoice_entity.exchange_rate, 6)
