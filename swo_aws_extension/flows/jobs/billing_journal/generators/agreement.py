from collections.abc import Callable
from typing import Any, cast

from mpt_extension_sdk.runtime.tracer import dynamic_trace_span

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.constants import (
    S3_BILLING_EXPORT_BUCKET_TEMPLATE,
    S3_BILLING_EXPORT_PREFIX_TEMPLATE,
    SupportTypesEnum,
)
<<<<<<< HEAD
from swo_aws_extension.flows.jobs.billing_journal.generators.cost_usage_report.usage import (
    CostUsageReportGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.discount.extra_discounts import (
    ExtraDiscountsManager,
)
=======
>>>>>>> 8a2540c (MPT-19081 Journals from AWS Billing with Cost and Usage Reports (WIP))
from swo_aws_extension.flows.jobs.billing_journal.generators.invoice import InvoiceGenerator
from swo_aws_extension.flows.jobs.billing_journal.generators.journal_line import (
    JournalLineGenerator,
)
<<<<<<< HEAD
from swo_aws_extension.flows.jobs.billing_journal.generators.pls_charge_manager import (
    PlSChargeManager,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.usage import (
=======
from swo_aws_extension.flows.jobs.billing_journal.generators.usage.generator import (
>>>>>>> 8a2540c (MPT-19081 Journals from AWS Billing with Cost and Usage Reports (WIP))
    BaseOrganizationUsageGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.usage.cost_usage_report.usage import (
    CostUsageReportGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.models.context import BillingJournalContext
from swo_aws_extension.flows.jobs.billing_journal.models.invoice import OrganizationInvoice
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

type AgreementData = dict[str, Any]
type TraceDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]

agreement_trace_span = cast(
    TraceDecorator,
    dynamic_trace_span(lambda _, agreement, **kwargs: f"Agreement {agreement.get('id')}"),
)


class AgreementJournalGenerator:
    """Generates journal lines and attachments for agreements."""

    def __init__(
        self,
        authorization_currency: str,
        context: BillingJournalContext,
        aws_client: AWSClient,
        pm_account_id: str,
        usage_generator: BaseOrganizationUsageGenerator | None = None,
    ) -> None:
        self._authorization_currency = authorization_currency
        self._pls_charge_percentage = context.pls_charge_percentage
        self._billing_period = context.billing_period
        self._aws_client = aws_client
        self._pm_account_id = pm_account_id
        self._usage_generator = usage_generator

    @with_log_context(lambda _, agreement, **kwargs: agreement.get("id"))
    @agreement_trace_span
    def run(self, agreement: AgreementData) -> AgreementJournalResult:
        """Generate billing journal lines for the given agreement.

        Args:
            agreement: The agreement data to process.

        Returns:
            AgreementJournalResult containing generated journal lines and usage report.
        """
        mpa_account = agreement.get("externalIds", {}).get("vendor", "")
        if not mpa_account:
            logger.info("No MPA account found for agreement: %s", agreement.get("id"))
            return AgreementJournalResult()

        invoice_result = InvoiceGenerator(self._aws_client).run(
            mpa_account,
            self._billing_period,
            self._authorization_currency,
        )
        logger.info("Found %d invoice entities", len(invoice_result.invoice.entities))

        usage_generator = self._usage_generator or CostUsageReportGenerator(
            self._aws_client,
            S3_BILLING_EXPORT_BUCKET_TEMPLATE.format(pm_account_id=self._pm_account_id),
            S3_BILLING_EXPORT_PREFIX_TEMPLATE.format(mpa_account_id=mpa_account),
        )
        usage_result = usage_generator.run(
            self._authorization_currency,
            mpa_account,
            self._billing_period,
            organization_invoice=invoice_result.invoice,
        )

        journal_details = JournalDetails(
            agreement_id=agreement.get("id", ""),
            mpa_id=mpa_account,
            start_date=self._billing_period.start_date,
            end_date=self._billing_period.last_day,
        )

        return self._generate_lines_for_accounts(
            agreement,
            usage_result,
            journal_details,
            invoice_result.invoice,
        )

    def _generate_lines_for_accounts(
        self,
        agreement: AgreementData,
        usage_result: OrganizationUsageResult,
        journal_details: JournalDetails,
        organization_invoice: OrganizationInvoice,
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

        all_lines.extend(
            ExtraDiscountsManager(self._pls_charge_percentage).process(
                agreement,
                usage_result,
                journal_details,
                organization_invoice,
            )
        )

        if is_pls:
            all_lines.extend(
                PlSChargeManager().process(
                    self._pls_charge_percentage,
                    usage_result,
                    journal_details,
                    organization_invoice,
                )
            )

        return AgreementJournalResult(lines=all_lines, report=usage_result.reports)
