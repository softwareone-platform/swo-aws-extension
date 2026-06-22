from typing import override

from swo_aws_extension.billing.generators.line_processors.base import JournalLineProcessor
from swo_aws_extension.billing.models.context import LineProcessorContext
from swo_aws_extension.billing.models.journal_line import JournalLine
from swo_aws_extension.billing.models.usage import ServiceMetric


class SavingsPlanJournalLineProcessor(JournalLineProcessor):
    """Processor for SavingsPlanRecurringFee lines.

    When split billing is enabled the recurring fee is distributed per linked account
    by SavingPlansDistributionProcessor, so this processor skips it to avoid double-billing.
    When split billing is disabled the fee goes to the master payer subscription via the
    default base processor behaviour.
    """

    @override
    def process(
        self,
        metric: ServiceMetric,
        context: LineProcessorContext,
    ) -> list[JournalLine]:
        if context.journal_details.split_billing_enabled:
            return []
        return super().process(metric, context)
