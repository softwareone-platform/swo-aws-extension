"""Result models for the AWS billing validation."""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from swo_aws_extension.billing.models.journal_result import (
    OrganizationSppSummaryRow,
)
from swo_aws_extension.billing.validation.models import (
    AgreementDiscounts,
    AgreementNames,
    MpaInvoices,
    ServiceSplit,
)
from swo_aws_extension.constants import DEC_ZERO


class ValidationStatus(StrEnum):
    """Outcome of validating one agreement."""

    OK = "OK"
    MISMATCH = "MISMATCH"
    MISSING_IN_PLATFORM = "MISSING_IN_PLATFORM"
    MISSING_INVOICES = "MISSING_INVOICES"


class DiscountKind(StrEnum):
    """Operations applied on top of the AWS cost price to reach the sales price."""

    SERVICE = "Service discount"
    SUPPORT = "Support discount"
    PLS_SUPPORT_REMOVED = "AWS Enterprise Support not charged (PLS)"
    PLS_CHARGE = "SWO Enterprise support for AWS (PLS)"
    PLS_DISCOUNT = "PLS discount"


@dataclass(frozen=True)
class DiscountStep:
    """One discount (or PLS adjustment) applied to the sales price."""

    kind: DiscountKind
    percentage: Decimal
    base: Decimal
    amount: Decimal
    base_label: str = ""

    @property
    def description(self) -> str:
        """Human readable description, e.g. ``Service discount 62.5% of SPP on usage``."""
        kind = self.kind.value
        if self.base_label:
            return f"{kind} {self.percentage}% of {self.base_label}"
        return kind


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
    steps: list[DiscountStep] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    invoices: MpaInvoices | None = None
    discounts: AgreementDiscounts | None = None
    split: ServiceSplit | None = None
    names: AgreementNames = field(default_factory=AgreementNames)

    def add_step(self, step: DiscountStep) -> None:
        """Record one discount applied to the sales price."""
        self.steps.append(step)
        self.sales_price += step.amount

    def step_amount(self, *kinds: DiscountKind) -> Decimal:
        """Total amount of the steps of the given kinds."""
        return sum((step.amount for step in self.steps if step.kind in kinds), DEC_ZERO)

    def step_percentage(self, kind: DiscountKind) -> Decimal | None:
        """Percentage of the step of the given kind, None when not applied."""
        step = next((step for step in self.steps if step.kind == kind), None)
        return step.percentage if step else None

    @property
    def total_discounts(self) -> Decimal:
        """Sum of every discount and PLS adjustment (negative when the customer pays less)."""
        return self.step_amount(*DiscountKind)

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
    likely_cause: str = ""
    names: AgreementNames = field(default_factory=AgreementNames)

    @property
    def failed_checks(self) -> list[CheckResult]:
        """Checks outside the tolerance."""
        return [check for check in self.checks if not check.ok]

    def check(self, name: str) -> CheckResult | None:
        """Check with the given name, None when not run."""
        return next((check for check in self.checks if check.name == name), None)
