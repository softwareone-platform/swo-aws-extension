from typing import override

from swo_aws_extension.flows.jobs.billing_journal.generators.line_processors.base import (
    JournalLineProcessor,
)
from swo_aws_extension.flows.jobs.billing_journal.models.context import LineProcessorContext
from swo_aws_extension.flows.jobs.billing_journal.models.journal_line import JournalLine
from swo_aws_extension.flows.jobs.billing_journal.models.usage import ServiceMetric

TAX_SERVICE_NAME = "Tax"


class MarketplaceJournalLineProcessor(JournalLineProcessor):
    """Generates journal lines for Marketplace metrics, excluding Tax entries."""

    @override
    def process(
        self,
        metric: ServiceMetric,
        context: LineProcessorContext,
    ) -> list[JournalLine]:
        """Process a marketplace metric, skipping Tax services.

        Args:
            metric: The service metric to process.
            context: Shared context for the current account.

        Returns:
            List of journal lines (empty if metric is Tax or should be skipped).
        """
        if metric.service_name == TAX_SERVICE_NAME:
            return []
        return super().process(metric, context)
