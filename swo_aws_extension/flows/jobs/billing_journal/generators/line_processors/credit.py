from swo_aws_extension.flows.jobs.billing_journal.generators.line_processors.base import (
    JournalLineProcessor,
)

CREDIT_PREFIX = "CREDIT - "


class CreditJournalLineProcessor(JournalLineProcessor):
    """Generates journal lines for Credit metrics with the CREDIT prefix.

    SPP recovery on zero invoices is handled independently by
    SppRecoveryJournalLineProcessor.
    """

    def __init__(self) -> None:
        super().__init__(prefix_name=CREDIT_PREFIX)
