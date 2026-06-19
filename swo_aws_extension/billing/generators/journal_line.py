from collections import defaultdict

from swo_aws_extension.billing.generators.line_processors.base import JournalLineProcessor
from swo_aws_extension.billing.generators.line_processors.bundle_discount import (
    BundleDiscountJournalLineProcessor,
)
from swo_aws_extension.billing.generators.line_processors.credit import CreditJournalLineProcessor
from swo_aws_extension.billing.generators.line_processors.marketplace import (
    MarketplaceJournalLineProcessor,
)
from swo_aws_extension.billing.generators.line_processors.support import SupportJournalLineProcessor
from swo_aws_extension.billing.models.context import LineProcessorContext
from swo_aws_extension.billing.models.invoice import OrganizationInvoice
from swo_aws_extension.billing.models.journal_line import JournalDetails, JournalLine
from swo_aws_extension.billing.models.usage import AccountUsage
from swo_aws_extension.constants import AWSRecordTypeEnum
from swo_aws_extension.logger import get_logger

logger = get_logger(__name__)

_IGNORED_RECORD_TYPES = frozenset((
    AWSRecordTypeEnum.TAX,
    AWSRecordTypeEnum.SOLUTION_PROVIDER_PROGRAM_DISCOUNT,
    AWSRecordTypeEnum.SAVING_PLAN_COVERED_USAGE,
    AWSRecordTypeEnum.SAVING_PLAN_NEGATION,
))


def _build_processor_registry() -> dict[str, JournalLineProcessor]:
    default = JournalLineProcessor()
    support = SupportJournalLineProcessor()
    credit = CreditJournalLineProcessor()
    marketplace = MarketplaceJournalLineProcessor()
    bundle_discount = BundleDiscountJournalLineProcessor()

    return defaultdict(
        lambda: default,
        {
            AWSRecordTypeEnum.SUPPORT: support,
            AWSRecordTypeEnum.CREDIT: credit,
            "MARKETPLACE": marketplace,
            AWSRecordTypeEnum.BUNDLE_DISCOUNT: bundle_discount,
        },
    )


class JournalLineGenerator:
    """Generates journal lines from account usage data using line processor."""

    def __init__(self, *, is_pls: bool = False) -> None:
        self._is_pls = is_pls
        self._processors = _build_processor_registry()

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
            is_pls=self._is_pls,
        )

        journal_lines: list[JournalLine] = []
        for metric in account_usage.metrics:
            if metric.record_type in _IGNORED_RECORD_TYPES:
                continue
            processor = self._processors[metric.record_type]
            journal_lines.extend(processor.process(metric, context))

        return journal_lines
