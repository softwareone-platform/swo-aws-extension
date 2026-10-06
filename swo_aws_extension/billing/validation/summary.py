"""Teams and log summaries of the billing validation."""

from collections import defaultdict
from decimal import Decimal

from swo_aws_extension.billing.validation.results import (
    AgreementValidation,
    ValidationStatus,
)
from swo_aws_extension.billing.validation.validator import SALES_PRICE_CHECK
from swo_aws_extension.constants import DEC_ZERO


def describe_issues(validations: list[AgreementValidation]) -> str | None:
    """Teams message with the summary and the agreements outside the tolerance.

    Returns None when every agreement matches.
    """
    issues = [entry for entry in validations if entry.status != ValidationStatus.OK]
    if not issues:
        return None
    details = "\n\n".join(f"• {describe_validation(validation)}" for validation in issues)
    return f"{summarize(validations)}\n\n{details}"


def summarize(validations: list[AgreementValidation]) -> str:
    """One paragraph: agreements validated, mismatches, no discounts and SP diff per currency."""
    mismatches = [entry for entry in validations if entry.status != ValidationStatus.OK]
    without_discounts = sum(1 for entry in validations if _has_no_discounts(entry))
    return (
        f"{len(validations)} agreement(s) validated, {len(mismatches)} outside the tolerance, "
        f"{without_discounts} without discounts configured. "
        f"SP difference per currency: {_sp_diff_per_currency(mismatches)} "
        "(see the Validation sheet of the billing report)."
    )


def _has_no_discounts(validation: AgreementValidation) -> bool:
    expected = validation.expected
    if expected is None or expected.discounts is None:
        return False
    return not expected.steps


def _sp_diff_per_currency(validations: list[AgreementValidation]) -> str:
    totals: dict[str, Decimal] = defaultdict(lambda: DEC_ZERO)
    for validation in validations:
        sales_check = validation.check(SALES_PRICE_CHECK)
        if sales_check is not None:
            totals[validation.currency] += sales_check.diff
    if not totals:
        return "none"
    return ", ".join(_format_total(entry) for entry in sorted(totals.items()))


def _format_total(entry: tuple[str, Decimal]) -> str:
    currency, total = entry
    return f"{total:.2f} {currency}"


def describe_validation(validation: AgreementValidation) -> str:
    """One line summary of a validation: agreement, status, failed checks and cause."""
    name = validation.names.agreement_name
    name = f" {name}" if name else ""
    failed = ", ".join(
        f"{check.name} diff {check.diff:.2f} {validation.currency}"
        for check in validation.failed_checks
    )
    status = validation.status.value
    parts = [
        f"{validation.agreement_id}{name} ({validation.mpa}): {status}",
        failed,
        validation.likely_cause,
        " | ".join(validation.notes),
    ]
    return " - ".join(part for part in parts if part)
