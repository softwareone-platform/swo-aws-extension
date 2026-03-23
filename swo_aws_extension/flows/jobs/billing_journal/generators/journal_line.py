from swo_aws_extension.constants import AWSRecordTypeEnum
from swo_aws_extension.flows.jobs.billing_journal.generators.line_processors.base import (
    JournalLineProcessor,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.line_processors.credit import (
    CreditJournalLineProcessor,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.line_processors.marketplace import (
    MarketplaceJournalLineProcessor,
)
from swo_aws_extension.flows.jobs.billing_journal.models.context import LineProcessorContext
from swo_aws_extension.flows.jobs.billing_journal.models.invoice import OrganizationInvoice
from swo_aws_extension.flows.jobs.billing_journal.models.journal_line import (
    JournalDetails,
    JournalLine,
)
from swo_aws_extension.flows.jobs.billing_journal.models.usage import AccountUsage
from swo_aws_extension.logger import get_logger

logger = get_logger(__name__)


def _build_processor_registry(*, is_pls: bool = False) -> dict[str, JournalLineProcessor]:
    default = JournalLineProcessor()
    credit = CreditJournalLineProcessor()
    marketplace = MarketplaceJournalLineProcessor()

    registry = {
        AWSRecordTypeEnum.USAGE: default,
        AWSRecordTypeEnum.SUPPORT: default,
        AWSRecordTypeEnum.RECURRING: default,
        AWSRecordTypeEnum.SAVING_PLAN_RECURRING_FEE: default,
        AWSRecordTypeEnum.CREDIT: credit,
        "MARKETPLACE": marketplace,
    }

    if is_pls:
        registry.pop(AWSRecordTypeEnum.SUPPORT, None)

    return registry


class JournalLineGenerator:
    """Generates journal lines from account usage data using line processors."""

    def __init__(self, *, is_pls: bool = False) -> None:
        self._processors = _build_processor_registry(is_pls=is_pls)

    def generate(
        self,
        account_id: str,
        account_usage: AccountUsage,
        journal_details: JournalDetails,
        organization_invoice: OrganizationInvoice,
    ) -> list[JournalLine]:
        """Generate journal lines for billable metrics in account usage.

        Args:
            account_id: The AWS account ID.
            account_usage: The account usage data containing service metrics.
            journal_details: Journal metadata details.
            organization_invoice: The organization invoice data.

        Returns:
            List of JournalLine objects for billable record types.
        """
        context = LineProcessorContext(
            account_id=account_id,
            account_usage=account_usage,
            journal_details=journal_details,
            organization_invoice=organization_invoice,
        )

        journal_lines: list[JournalLine] = []
        for metric in account_usage.metrics:
            processor = self._processors.get(metric.record_type)
            if processor:
                journal_lines.extend(processor.process(metric, context))

        return journal_lines
