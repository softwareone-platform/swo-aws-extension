"""Result models for the AWS billing validation."""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from swo_aws_extension.constants import DEC_ZERO
from swo_aws_extension.flows.jobs.billing_journal.models.journal_result import (
    OrganizationSppSummaryRow,
)
from swo_aws_extension.flows.jobs.billing_validation.models import (
    AgreementDiscounts,
    MpaInvoices,
    ServiceSplit,
)

BASE_STEPS = 2


class ValidationStatus(StrEnum):
    """Outcome of validating one agreement."""

    OK = "OK"
    MISMATCH = "MISMATCH"
    MISSING_IN_PLATFORM = "MISSING_IN_PLATFORM"
    MISSING_INVOICES = "MISSING_INVOICES"


@dataclass
class ExpectedBilling:
    """Expected prices for one agreement following the manual validation operations."""

    agreement_id: str
    mpa: str
    pma: str
    authorization_id: str
    currency: str
    cost_price: Decimal = DEC_ZERO
    list_price: Decimal = DEC_ZERO
    spp_discount: Decimal = DEC_ZERO
    sales_price: Decimal = DEC_ZERO
    steps: list[tuple[str, Decimal]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    invoices: MpaInvoices | None = None
    discounts: AgreementDiscounts | None = None
    split: ServiceSplit | None = None

    def add_step(self, description: str, amount: Decimal) -> None:
        """Record one operation applied to the sales price."""
        self.steps.append((description, amount))
        self.sales_price += amount

    @property
    def discount_steps(self) -> list[tuple[str, Decimal]]:
        """Operations other than the cost price and the SPP discount kept by SWO."""
        return self.steps[BASE_STEPS:]

    @property
    def markup(self) -> Decimal:
        """Expected agreement markup (SP - PP) / PP."""
        if not self.cost_price:
            return DEC_ZERO
        return (self.sales_price - self.cost_price) / self.cost_price


@dataclass(frozen=True)
class CheckResult:
    """Comparison of one expected value against the platform value."""

    name: str
    expected: Decimal
    actual: Decimal
    tolerance: Decimal

    @property
    def diff(self) -> Decimal:
        """Platform value minus expected value."""
        return self.actual - self.expected

    @property
    def ok(self) -> bool:
        """Whether the difference is within the tolerance."""
        return abs(self.diff) <= self.tolerance


@dataclass
class AgreementValidation:
    """Validation outcome for one agreement."""

    agreement_id: str
    mpa: str
    pma: str
    authorization_id: str
    currency: str
    status: ValidationStatus
    expected: ExpectedBilling | None = None
    platform: OrganizationSppSummaryRow | None = None
    checks: list[CheckResult] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    tolerance: Decimal | None = None

    @property
    def failed_checks(self) -> list[CheckResult]:
        """Checks outside the tolerance."""
        return [check for check in self.checks if not check.ok]
