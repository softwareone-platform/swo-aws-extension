from mpt_extension_sdk.runtime.tracer import dynamic_trace_span

from swo_aws_extension.constants import SupportTypesEnum
from swo_aws_extension.flows.jobs.billing_journal.generators.discount.extra_discounts import (
    ExtraDiscountsManager,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.invoice import InvoiceGenerator
from swo_aws_extension.flows.jobs.billing_journal.generators.journal_line import (
    JournalLineGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.pls_charge_manager import (
    PlSChargeManager,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.usage import (
    BaseOrganizationUsageGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.models.context import BillingJournalContext
from swo_aws_extension.flows.jobs.billing_journal.models.journal_line import (
    JournalDetails,
    JournalLine,
)
from swo_aws_extension.flows.jobs.billing_journal.models.journal_result import (
    AgreementJournalResult,
)
from swo_aws_extension.flows.jobs.billing_journal.models.usage import OrganizationUsageResult
from swo_aws_extension.logger import get_logger
from swo_aws_extension.parameters import get_support_type
from swo_aws_extension.utils.decorators import with_log_context

logger = get_logger(__name__)


class AgreementJournalGenerator:
    """Generates journal lines and attachments for Agreements."""

    def __init__(
        self,
        authorization_currency: str,
        context: BillingJournalContext,
        usage_generator: BaseOrganizationUsageGenerator,
        invoice_generator: InvoiceGenerator,
    ) -> None:
        self._authorization_currency = authorization_currency
        self._pls_charge_percentage = context.pls_charge_percentage
        self._config = context.config
        self._mpt_client = context.mpt_client
        self._billing_period = context.billing_period
        self._usage_generator = usage_generator
        self._invoice_generator = invoice_generator

    @with_log_context(lambda _, agreement, **kwargs: agreement.get("id"))
    @dynamic_trace_span(lambda _, agreement, **kwargs: f"Agreement {agreement.get('id')}")
    def run(self, agreement: dict) -> AgreementJournalResult:
        """Generate billing journal lines for the given agreement.

        Args:
            agreement: The agreement data to process.

        Returns:
            AgreementJournalResult object containing a list of JournalLine objects and reports.
        """
        mpa_account = agreement.get("externalIds", {}).get("vendor", "")
        if not mpa_account:
            logger.info("No MPA account found for agreement. Skipping journal generation.")
            return AgreementJournalResult()

        logger.info("Generating billing journal for MPA account %s", mpa_account)
        invoice_result = self._invoice_generator.run(
            mpa_account,
            self._billing_period,
            self._authorization_currency,
        )
        logger.info(
            "Found %d invoice entities",
            len(invoice_result.invoice.entities),
        )

        usage_result = self._usage_generator.run(
            self._authorization_currency,
            mpa_account,
            self._billing_period,
            organization_invoice=invoice_result.invoice,
        )
        logger.info("Usage generation completed for MPA account %s", mpa_account)

        journal_details = JournalDetails(
            agreement_id=agreement.get("id", ""),
            mpa_id=mpa_account,
            start_date=self._billing_period.start_date,
            end_date=self._billing_period.last_day,
        )

        agreement_result = self._generate_lines_for_accounts(
            agreement,
            usage_result,
            journal_details,
            invoice_result.invoice,
        )
        logger.info("Generated %d journal lines", len(agreement_result.lines))
        return agreement_result

    def _generate_lines_for_accounts(
        self,
        agreement: dict,
        usage_result: OrganizationUsageResult,
        journal_details: JournalDetails,
        organization_invoice,
    ) -> AgreementJournalResult:
        is_pls = get_support_type(agreement) == SupportTypesEnum.AWS_RESOLD_SUPPORT
        line_generator = JournalLineGenerator(is_pls=is_pls)

        all_lines: list[JournalLine] = []
        for account_id, account_usage in usage_result.usage_by_account.items():
            all_lines.extend(
                line_generator.generate(
                    account_id,
                    account_usage,
                    journal_details,
                    organization_invoice,
                )
            )

        # Process extra discounts after generating all usage lines.
        all_lines.extend(
            ExtraDiscountsManager(self._pls_charge_percentage).process(
                agreement,
                usage_result,
                journal_details,
                organization_invoice,
            )
        )

        # If PLS is active, calculate and add the PLS charge line.
        if is_pls:
            all_lines.extend(
                PlSChargeManager().process(
                    self._pls_charge_percentage,
                    usage_result,
                    journal_details,
                    organization_invoice,
                )
            )

        return AgreementJournalResult(
            lines=all_lines,
            report=usage_result.reports,
        )
