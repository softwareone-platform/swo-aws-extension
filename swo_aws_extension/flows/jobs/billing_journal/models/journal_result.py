from dataclasses import dataclass, field

from swo_aws_extension.flows.jobs.billing_journal.models.journal_line import JournalLine
from swo_aws_extension.flows.jobs.billing_journal.models.usage import OrganizationReport


@dataclass
class AgreementJournalResult:
    """Result of generating an agreement journal."""

    lines: list[JournalLine] = field(default_factory=list)
    report: OrganizationReport | None = None


@dataclass
class AuthorizationJournalResult:
    """Result of generating an authorization journal."""

    lines: list[JournalLine] = field(default_factory=list)
    reports_by_agreement: dict[str, OrganizationReport] = field(default_factory=dict)
