from typing import override

from swo_aws_extension.billing.generators.line_processors.base import (
    JournalLineProcessor,
)
from swo_aws_extension.billing.models.context import LineProcessorContext
from swo_aws_extension.billing.models.usage import ServiceMetric
from swo_aws_extension.constants import ItemSkuEnum

CREDIT_PREFIX = "CREDIT - "


class CreditJournalLineProcessor(JournalLineProcessor):
    """Generates journal lines for Credit metrics with the CREDIT prefix.

    SPP recovery on zero invoices is handled independently by
    SppRecoveryJournalLineProcessor.
    """

    item_sku: str = ItemSkuEnum.ADDITIONAL_CHARGES_SKU

    def __init__(self) -> None:
        super().__init__(prefix_name=CREDIT_PREFIX)

    @override
    def _resolve_sku(self, metric: ServiceMetric, context: LineProcessorContext) -> str:
        return ItemSkuEnum.ADDITIONAL_CHARGES_SKU.value
