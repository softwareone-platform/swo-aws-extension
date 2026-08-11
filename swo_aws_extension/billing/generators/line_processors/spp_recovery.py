from typing import override

from swo_aws_extension.billing.generators.line_processors.base import (
    JournalLineProcessor,
)
from swo_aws_extension.billing.models.context import LineProcessorContext
from swo_aws_extension.billing.models.journal_line import JournalLine
from swo_aws_extension.billing.models.usage import ServiceMetric
from swo_aws_extension.constants import DEC_ZERO, ItemSkuEnum

SPP_PREFIX = "SPP - "
SPP_SUFFIX = (
    " - Invoice amount is 0 with credits applied. The SPP value will not be "
    "charged to the customer."
)


class SppRecoveryJournalLineProcessor(JournalLineProcessor):
    """Generates SPP recovery lines in zero-invoice credit scenarios.

    The SPP discount is the provider benefit and is normally excluded from the
    journal. When the principal invoice amount is zero (usage fully covered by
    credits), every SPP metric is returned to the customer so the journal
    reconciles to the zero invoice, including SPP on usage whose credit is
    reported under a different service.
    """

    def __init__(self) -> None:
        super().__init__(prefix_name=SPP_PREFIX, suffix_name=SPP_SUFFIX)

    @override
    def process(
        self,
        metric: ServiceMetric,
        context: LineProcessorContext,
    ) -> list[JournalLine]:
        """Process an SPP metric, only returned to the customer on zero invoices.

        Args:
            metric: The service metric to process.
            context: Shared context for the current account.

        Returns:
            List of journal lines (empty unless the principal invoice amount is zero).
        """
        if context.organization_invoice.principal_invoice_amount != DEC_ZERO:
            return []
        return super().process(metric, context)

    @override
    def _resolve_sku(self, metric: ServiceMetric, context: LineProcessorContext) -> str:
        return ItemSkuEnum.ADDITIONAL_CHARGES_SKU.value
