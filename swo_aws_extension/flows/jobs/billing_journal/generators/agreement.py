import datetime as dt

from mpt_extension_sdk.runtime.tracer import dynamic_trace_span

from swo_aws_extension.constants import (
    DEC_ZERO,
    ResponsibilityTransferStatus,
    SupportTypesEnum,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.billing_report_rows import (
    BillingReportRowsBuilder,
    ReportContext,
    build_spp_summary_row,
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


def calculate_markup(
    all_lines: list[JournalLine],
    organization_invoice,
    context: ReportContext,
):
    """Compute the dynamic markup reconciling the journal total (sp) against the invoice (pp).

    This must run once the journal lines for the agreement exist and before they are
    rewritten by ``apply_markup_to_lines``, since it reads their current (usage-based)
    price. The resulting value feeds both the report row and the journal rewrite.
    """
    sp = sum((line.price.pp_x1 for line in all_lines if line.is_valid()), DEC_ZERO)
    pp = (
        organization_invoice.base_total_amount_before_tax
        if context.currency == "USD"
        else organization_invoice.payment_currency_total_amount_before_tax
    )
    return (sp - pp) / pp if pp else DEC_ZERO


def apply_markup_to_lines(lines: list[JournalLine], markup) -> None:
    """Rewrite each valid line's price as the invoice-derived purchase price.

    Lines are priced up front as the usage-based sales amount (sp). The
    billing platform doesn't support per-service dynamic markups, so instead
    we upload the purchase price (pp) per line and set this same agreement-
    level markup on the platform; it then recomputes sp = pp * (1 + markup)
    itself. Dividing every line by (1 + markup) rewrites the total from sp
    down to pp while preserving each line's relative share, so the platform's
    own calculation reconstructs the original sp exactly.
    """
    divisor = 1 + markup
    if divisor <= DEC_ZERO:
        return
    for line in lines:
        if not line.is_valid():
            continue
        line.price.pp_x1 = round(line.price.pp_x1 / divisor, 6)
        line.price.unit_pp = round(line.price.unit_pp / divisor, 6)


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
            self._auth_context.pma_account,
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
        usage_result.reports.organization_data["INVOICES"] = invoice_result.raw_data
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
            invoice_result.invoice_ids,
        )
        logger.info("Generated %d journal lines", len(agreement_result.lines))
        return agreement_result

    def _generate_lines_for_accounts(
        self,
        agreement: dict,
        usage_result: OrganizationUsageResult,
        journal_details: JournalDetails,
        organization_invoice,
        invoice_ids: set[str],
    ) -> AgreementJournalResult:
        pls_in_order = get_support_type(agreement) == SupportTypesEnum.PARTNER_LED_SUPPORT
        report_has_enterprise = usage_result.has_enterprise_support()

        all_lines = self._generate_usage_lines(
            is_pls=pls_in_order and report_has_enterprise,
            usage_result=usage_result,
            journal_details=journal_details,
            organization_invoice=organization_invoice,
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

        pls_mismatches: list[PlsMismatch] = []
        if pls_in_order != report_has_enterprise:
            pls_mismatches.append(
                PlsMismatch(
                    agreement_id=agreement.get("id", ""),
                    pls_in_order=pls_in_order,
                    report_has_enterprise=report_has_enterprise,
                )
            )

        if pls_in_order and report_has_enterprise:
            all_lines.extend(
                PlSChargeManager().process(
                    self._pls_charge_percentage,
                    usage_result,
                    journal_details,
                    organization_invoice,
                )
            )

        result = self._build_agreement_journal_result(
            all_lines,
            journal_details,
            organization_invoice,
            usage_result,
        )
        result.invoice_ids = invoice_ids
        result.pls_mismatches = pls_mismatches
        return result

    def _build_agreement_journal_result(
        self,
        all_lines: list[JournalLine],
        journal_details: JournalDetails,
        organization_invoice,
        usage_result: OrganizationUsageResult,
    ) -> AgreementJournalResult:
        context = ReportContext.from_contexts(self._auth_context, journal_details)
        report_builder = BillingReportRowsBuilder(context, usage_result, organization_invoice)
        billing_report_rows = report_builder.build()

        markup = calculate_markup(all_lines, organization_invoice, context)
        spp_summary_row = build_spp_summary_row(
            context, all_lines, billing_report_rows, organization_invoice, markup
        )
        apply_markup_to_lines(all_lines, markup)

        return AgreementJournalResult(
            lines=all_lines,
            report=usage_result.reports,
            billing_report_rows=billing_report_rows,
            billing_report_rows_by_account=report_builder.build_by_account(),
            spp_summary_row=spp_summary_row,
        )

    def _generate_usage_lines(
        self,
        *,
        is_pls: bool,
        usage_result: OrganizationUsageResult,
        journal_details: JournalDetails,
        organization_invoice,
    ) -> list[JournalLine]:
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
