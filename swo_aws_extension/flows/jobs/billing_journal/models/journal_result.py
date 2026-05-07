from dataclasses import dataclass, field
from decimal import Decimal

from swo_aws_extension.flows.jobs.billing_journal.models.journal_line import JournalLine
from swo_aws_extension.flows.jobs.billing_journal.models.usage import OrganizationReport


@dataclass
class BillingReportRow:
    """Row data for the Excel billing report."""

    authorization_id: str
    pma: str
    agreement_id: str
    mpa: str
    service_name: str
    amount: Decimal
    currency: str
    invoice_id: str
    invoice_entity: str
    exchange_rate: Decimal
    spp_discount: Decimal


@dataclass
class PlsMismatch:
    """Records a PLS mismatch between order parameter and usage report."""

    agreement_id: str
    pls_in_order: bool
    report_has_enterprise: bool

    @property
    def description(self) -> str:
        """Description of the mismatch for reporting purposes."""
        param_label = "PLS" if self.pls_in_order else "Resold Support"
        report_label = "has" if self.report_has_enterprise else "does not have"
        return (
            f"Agreement {self.agreement_id}: parameter={param_label} "
            f"but report {report_label} 'AWS Support (Enterprise)'."
        )


@dataclass
class AgreementJournalResult:
    """Result of generating an agreement journal."""

    lines: list[JournalLine] = field(default_factory=list)
    report: OrganizationReport | None = None
    billing_report_rows: list[BillingReportRow] = field(default_factory=list)
    pls_mismatches: list[PlsMismatch] = field(default_factory=list)


@dataclass
class AuthorizationJournalResult:
    """Result of generating an authorization journal."""

    lines: list[JournalLine] = field(default_factory=list)
    reports_by_agreement: dict[str, OrganizationReport] = field(default_factory=dict)
    billing_report_rows: list[BillingReportRow] = field(default_factory=list)
    pls_mismatches: list[PlsMismatch] = field(default_factory=list)
