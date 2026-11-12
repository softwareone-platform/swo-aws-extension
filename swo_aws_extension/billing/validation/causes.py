"""Guess the most likely cause of a billing validation mismatch.

The guesses follow the cases found while reconciling the manual sheet with the
platform: missing discount parameters, invoices the platform used but
the manual sheet did not (or the other way round), and Cost Explorer usage arriving
after the invoice was issued.
"""

from decimal import Decimal

from swo_aws_extension.billing.validation.results import (
    AgreementValidation,
    ExpectedBilling,
)
from swo_aws_extension.constants import DEC_ZERO

LATE_USAGE_RATIO = Decimal("0.01")
COST_PRICE_MISMATCH = (
    "Platform cost price differs from the AWS invoices of the MPA: check the invoice IDs "
    "used by the journal (duplicated or foreign marketplace invoices)."
)
NO_DISCOUNTS_IN_PLATFORM = (
    "Platform SP equals cost price plus the full SPP discount: the expected discounts "
    "were not applied by the journal."
)
DISCOUNTS_NOT_EXPECTED = (
    "Platform SP is lower than the expected one by the full SPP discount: the journal "
    "applied discounts the agreement parameters do not configure."
)
LESS_USAGE = (
    "Cost Explorer reports less metered usage than the final invoice (usage arriving "
    "late); re-run in a few days."
)
MORE_USAGE = "Cost Explorer reports more usage than the final invoice: check credits or refunds."
UNEXPLAINED = (
    "Journal total built from Cost Explorer does not match: check credits, refunds or "
    "unbilled record types."
)


def explain_mismatch(validation: AgreementValidation) -> str:
    """Return a one line guess of why the agreement does not match."""
    expected = validation.expected
    platform = validation.platform
    if expected is None or platform is None:
        return ""
    first_failed = validation.failed_checks[0]
    if first_failed.name.startswith("Cost price"):
        return COST_PRICE_MISMATCH
    return _explain_sales_price(validation, first_failed.diff)


def _explain_sales_price(validation: AgreementValidation, diff: Decimal) -> str:
    expected = validation.expected
    tolerance = validation.tolerance or DEC_ZERO
    if expected is None or expected.discounts is None:
        return "Agreement not found in the platform: no discounts could be applied."
    guesses = _guesses(expected, diff, tolerance)
    return next((message for matches, message in guesses if matches), UNEXPLAINED)


def _guesses(expected: ExpectedBilling, diff: Decimal, tolerance: Decimal) -> tuple:
    missing_discounts = abs(diff - abs(expected.total_discounts)) <= tolerance
    return (
        (bool(expected.steps) and missing_discounts, NO_DISCOUNTS_IN_PLATFORM),
        (abs(diff + abs(expected.spp_discount)) <= tolerance, DISCOUNTS_NOT_EXPECTED),
        (abs(diff) <= abs(expected.sales_price) * LATE_USAGE_RATIO, _usage_guess(diff)),
    )


def _usage_guess(diff: Decimal) -> str:
    return LESS_USAGE if diff < DEC_ZERO else MORE_USAGE
