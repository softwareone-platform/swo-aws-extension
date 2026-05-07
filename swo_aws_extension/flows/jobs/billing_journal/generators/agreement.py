import datetime as dt

from mpt_extension_sdk.runtime.tracer import dynamic_trace_span

from swo_aws_extension.constants import ResponsibilityTransferStatus, SupportTypesEnum
from swo_aws_extension.flows.jobs.billing_journal.generators.billing_report_rows import (
    ReportContext,
    generate_billing_report_rows,
)
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
from swo_aws_extension.flows.jobs.billing_journal.models.context import (
    AuthorizationContext,
    BillingJournalContext,
)
from swo_aws_extension.flows.jobs.billing_journal.models.journal_line import (
    JournalDetails,
    JournalLine,
)
from swo_aws_extension.flows.jobs.billing_journal.models.journal_result import (
    AgreementJournalResult,
    PlsMismatch,
)
from swo_aws_extension.flows.jobs.billing_journal.models.usage import OrganizationUsageResult
from swo_aws_extension.logger import get_logger
from swo_aws_extension.parameters import get_responsibility_transfer_id, get_support_type
from swo_aws_extension.utils.decorators import with_log_context

logger = get_logger(__name__)


class AgreementJournalGenerator:
    """Generates journal lines and attachments for Agreements."""

    def __init__(
        self,
        auth_context: AuthorizationContext,
        context: BillingJournalContext,
        usage_generator: BaseOrganizationUsageGenerator,
        invoice_generator: InvoiceGenerator,
    ) -> None:
        self._auth_context = auth_context
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

        if not self._validate_agreement(agreement, mpa_account):
            return AgreementJournalResult()

        logger.info("Generating billing journal for MPA account %s", mpa_account)
        invoice_result = self._invoice_generator.run(
            mpa_account,
            self._billing_period,
            self._auth_context.currency,
        )

        usage_result = self._usage_generator.run(
            self._auth_context.currency,
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
        all_lines = self._generate_usage_lines(usage_result, journal_details, organization_invoice)

        # Process extra discounts after generating all usage lines.
        all_lines.extend(
            ExtraDiscountsManager(self._pls_charge_percentage).process(
                agreement,
                usage_result,
                journal_details,
                organization_invoice,
            )
        )

        pls_in_order = get_support_type(agreement) == SupportTypesEnum.PARTNER_LED_SUPPORT
        report_has_enterprise = usage_result.has_enterprise_support()

        pls_mismatches: list[PlsMismatch] = []
        if pls_in_order != report_has_enterprise:
            pls_mismatches.append(
                PlsMismatch(
                    agreement_id=agreement.get("id", ""),
                    pls_in_order=pls_in_order,
                    report_has_enterprise=report_has_enterprise,
                )
            )

        if report_has_enterprise:
            all_lines.extend(
                PlSChargeManager().process(
                    self._pls_charge_percentage,
                    usage_result,
                    journal_details,
                    organization_invoice,
                )
            )

        report_rows = generate_billing_report_rows(
            context=ReportContext.from_contexts(self._auth_context, journal_details),
            usage_result=usage_result,
            organization_invoice=organization_invoice,
        )

        return AgreementJournalResult(
            lines=all_lines,
            report=usage_result.reports,
            billing_report_rows=report_rows,
            pls_mismatches=pls_mismatches,
        )

    def _generate_usage_lines(
        self,
        usage_result: OrganizationUsageResult,
        journal_details: JournalDetails,
        organization_invoice,
    ) -> list[JournalLine]:
        is_pls = usage_result.has_enterprise_support()
        line_generator = JournalLineGenerator(is_pls=is_pls)

        lines: list[JournalLine] = []
        for account_id, account_usage in usage_result.usage_by_account.items():
            lines.extend(
                line_generator.generate(
                    account_id,
                    account_usage,
                    journal_details,
                    organization_invoice,
                )
            )
        return lines

    def _validate_agreement(self, agreement, mpa_account):
        if not mpa_account:
            logger.info("No MPA account found for agreement. Skipping journal generation.")
            return False

        responsibility_transfer_id = get_responsibility_transfer_id(agreement)
        responsibility_transfer = self._auth_context.aws_client.get_responsibility_transfer_details(
            responsibility_transfer_id,
        )

        status = responsibility_transfer.get("ResponsibilityTransfer", {}).get("Status")
        if status != ResponsibilityTransferStatus.ACCEPTED:
            logger.info(
                "%s - Skipping because responsibility transfer invitation is not"
                " accepted. Current status: %s",
                agreement.get("id"),
                status,
            )
            return False

        start_timestamp = responsibility_transfer.get("ResponsibilityTransfer", {}).get(
            "StartTimestamp"
        )
        billing_start = dt.datetime.strptime(
            self._billing_period.start_date,
            "%Y-%m-%d",
        ).replace(tzinfo=dt.UTC)
        if start_timestamp and start_timestamp > billing_start:
            logger.info(
                "%s - Skipping agreement because responsibility transfer has not started yet. "
                "Start date: %s",
                agreement.get("id"),
                start_timestamp,
            )
            return False
        return True
