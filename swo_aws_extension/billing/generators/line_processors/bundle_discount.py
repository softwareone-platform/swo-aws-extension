from typing import override

from swo_aws_extension.billing.generators.line_processors.base import (
    JournalLineProcessor,
)
from swo_aws_extension.billing.models.context import LineProcessorContext
from swo_aws_extension.billing.models.journal_line import JournalLine
from swo_aws_extension.billing.models.usage import ServiceMetric

BUNDLE_DISCOUNT_PREFIX = "Bundled_Discount_"


class BundleDiscountJournalLineProcessor(JournalLineProcessor):
    """Generates journal lines for Bundle Discount metrics.

    Always generates a line with the Bundled_Discount_ prefix.
    """

    def __init__(self) -> None:
        super().__init__(prefix_name=BUNDLE_DISCOUNT_PREFIX)

    @override
    def process(
        self,
        metric: ServiceMetric,
        context: LineProcessorContext,
    ) -> list[JournalLine]:
        return super().process(metric, context)
