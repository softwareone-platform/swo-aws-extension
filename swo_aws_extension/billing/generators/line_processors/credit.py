from typing import override

from swo_aws_extension.billing.generators.line_processors.base import (
    JournalLineProcessor,
)
from swo_aws_extension.billing.models.context import LineProcessorContext
from swo_aws_extension.billing.models.journal_line import JournalLine
from swo_aws_extension.billing.models.usage import AccountUsage, ServiceMetric
from swo_aws_extension.constants import DEC_ZERO, AWSRecordTypeEnum, ItemSkuEnum

CREDIT_PREFIX = "CREDIT - "
SPP_PREFIX = "SPP - "
SPP_SUFFIX = (
    " - Invoice amount is 0 with credits applied. The SPP value will not be "
    "charged to the customer."
)


class SppRecoveryJournalLineProcessor(JournalLineProcessor):
    """Generates SPP recovery lines in zero-invoice credit scenarios."""

    def __init__(self) -> None:
        super().__init__(prefix_name=SPP_PREFIX, suffix_name=SPP_SUFFIX)

    @override
    def _resolve_sku(self, metric: ServiceMetric, context: LineProcessorContext) -> str:
        return ItemSkuEnum.ADDITIONAL_CHARGES_SKU.value


class CreditJournalLineProcessor(JournalLineProcessor):
    """Generates journal lines for Credit metrics.

    Always generates a credit line with the CREDIT prefix. When the principal invoice amount is
    zero, also generates an SPP discount line to return the SPP provider benefit to the customer.
    """

    item_sku: str = ItemSkuEnum.ADDITIONAL_CHARGES_SKU

    def __init__(self) -> None:
        super().__init__(prefix_name=CREDIT_PREFIX)
        self._spp_processor = SppRecoveryJournalLineProcessor()

    @override
    def process(
        self,
        metric: ServiceMetric,
        context: LineProcessorContext,
    ) -> list[JournalLine]:
        lines = super().process(metric, context)
        if not lines:
            return lines

        if self._should_add_spp_line(context):
            spp_metric = self._find_spp_for_service(
                context.account_usage, metric.service_name, metric.start_date, metric.end_date
            )
            if spp_metric:
                lines.extend(self._spp_processor.process(spp_metric, context))

        return lines

    @override
    def _resolve_sku(self, metric: ServiceMetric, context: LineProcessorContext) -> str:
        return ItemSkuEnum.ADDITIONAL_CHARGES_SKU.value

    def _should_add_spp_line(self, context: LineProcessorContext) -> bool:
        principal_amount = context.organization_invoice.principal_invoice_amount
        return principal_amount == DEC_ZERO

    def _find_spp_for_service(
        self, account_usage: AccountUsage, service_name: str, start_date: str, end_date: str
    ) -> ServiceMetric | None:
        spp_metrics = [
            metric
            for metric in account_usage.get_metrics_by_service(service_name)
            if metric.record_type == AWSRecordTypeEnum.SOLUTION_PROVIDER_PROGRAM_DISCOUNT
            and metric.start_date == start_date
            and metric.end_date == end_date
        ]
        return spp_metrics[0] if spp_metrics else None
