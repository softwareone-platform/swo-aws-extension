from swo_aws_extension.billing.generators.line_processors.base import (
    JournalLineProcessor,
)
from swo_aws_extension.billing.models.context import LineProcessorContext
from swo_aws_extension.billing.models.journal_line import JournalLine
from swo_aws_extension.billing.models.usage import ServiceMetric


class SupportJournalLineProcessor(JournalLineProcessor):
    """Processor for AWS Support lines."""

    def process(
        self,
        metric: ServiceMetric,
        context: LineProcessorContext,
    ) -> list[JournalLine]:
        """Process AWS Support lines, omitting Enterprise Support if PLS is active."""
        if context.is_pls and metric.service_name == "AWS Support (Enterprise)":
            return []
        return super().process(metric, context)
