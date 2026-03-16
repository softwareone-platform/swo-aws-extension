from mpt_extension_sdk.runtime.tracer import dynamic_trace_span

from swo_aws_extension.flows.jobs.billing_journal.generators.journal_line import (
    JournalLineGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.usage import (
    BaseOrganizationUsageGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.models.context import BillingJournalContext
from swo_aws_extension.flows.jobs.billing_journal.models.journal_line import (
    JournalDetails,
    JournalLine,
)
from swo_aws_extension.flows.jobs.billing_journal.models.usage import OrganizationUsageResult
from swo_aws_extension.logger import get_logger
from swo_aws_extension.utils.decorators import with_log_context

logger = get_logger(__name__)


class AgreementJournalGenerator:
    """Generates journal lines and attachments for Agreements."""

    def __init__(
        self,
        authorization_currency: str,
        context: BillingJournalContext,
        usage_generator: BaseOrganizationUsageGenerator,
    ) -> None:
        self._authorization_currency = authorization_currency
        self._config = context.config
        self._mpt_client = context.mpt_client
        self._billing_period = context.billing_period
        self._usage_generator = usage_generator

    @with_log_context(lambda _, agreement, **kwargs: agreement.get("id"))
    @dynamic_trace_span(lambda _, agreement, **kwargs: f"Agreement {agreement.get('id')}")
    def run(self, agreement: dict) -> list[JournalLine]:
        """Generate journal lines for the given agreement.

        Args:
            agreement: The agreement data to process.

        Returns:
            List of JournalLine objects.
        """
        mpa_account = agreement.get("externalIds", {}).get("vendor", "")
        if not mpa_account:
            logger.info("No PMA account found for agreement: %s", agreement.get("id"))
            return []

        usage_result = self._usage_generator.run(
            self._authorization_currency, mpa_account, self._billing_period
        )

        journal_details = JournalDetails(
            agreement_id=agreement.get("id", ""),
            mpa_id=mpa_account,
            start_date=self._billing_period.start_date,
            end_date=self._billing_period.last_day,
        )

        return self._generate_lines_for_accounts(usage_result, journal_details)

    def _generate_lines_for_accounts(
        self,
        usage_result: OrganizationUsageResult,
        journal_details: JournalDetails,
    ) -> list[JournalLine]:
        line_generator = JournalLineGenerator()
        all_lines: list[JournalLine] = []
        for account_id, account_usage in usage_result.usage_by_account.items():
            all_lines.extend(line_generator.generate(account_id, account_usage, journal_details))
        return all_lines
