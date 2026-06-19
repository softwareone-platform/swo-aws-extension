from swo_aws_extension.billing.generators.currency import resolve_service_amount
from swo_aws_extension.billing.models.context import LineProcessorContext
from swo_aws_extension.billing.models.journal_line import InvoiceDetails, JournalLine
from swo_aws_extension.billing.models.usage import ServiceMetric
from swo_aws_extension.constants import DEC_ZERO, AWSRecordTypeEnum, ItemSkuEnum


class JournalLineProcessor:
    """Base class for all line processor."""

    is_organization_charge: bool = False

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

    def _resolve_sku(self, metric: ServiceMetric, context: LineProcessorContext) -> str:
        """Resolve the item SKU based on SPP discount presence for the service.

        Routes to USAGE_SKU for services with a non-zero SPP discount (AWS usage-like services),
        and to ADDITIONAL_CHARGES_SKU for everything else.
        """
        spp_metrics = context.account_usage.get_metrics_by_service(metric.service_name)
        has_spp = any(
            spp_metric.record_type == AWSRecordTypeEnum.SOLUTION_PROVIDER_PROGRAM_DISCOUNT
            and spp_metric.amount != DEC_ZERO
            for spp_metric in spp_metrics
        )
        return ItemSkuEnum.USAGE_SKU if has_spp else ItemSkuEnum.ADDITIONAL_CHARGES_SKU

    def _build_line(
        self,
        metric: ServiceMetric,
        context: LineProcessorContext,
    ) -> JournalLine:
        service_name = f"{self._prefix_name}{metric.service_name}{self._suffix_name}"
        invoice_entity = context.organization_invoice.entities.get(metric.invoice_entity or "")
        service_amount = resolve_service_amount(metric.amount, invoice_entity)
        invoice_details = InvoiceDetails(
            service_name=service_name,
            amount=service_amount,
            account_id=context.account_id,
            invoice_entity=metric.invoice_entity or "",
            invoice_id=metric.invoice_id or "invoice_id",
            start_date=metric.start_date,
            end_date=metric.end_date,
        )
        return JournalLine.build(
            self._resolve_sku(metric, context),
            context.journal_details,
            invoice_details,
            is_organization_charge=self.is_organization_charge,
        )
