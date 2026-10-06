"""Rows of the ``Validation`` sheet added to the monthly billing report."""

from decimal import Decimal

from swo_aws_extension.flows.jobs.billing_validation.results import (
    AgreementValidation,
    ValidationStatus,
)
from swo_aws_extension.flows.jobs.billing_validation.validator import SALES_PRICE_CHECK

VALIDATION_HEADERS = (
    "Authorization ID",
    "PMA",
    "Agreement ID",
    "MPA",
    "Currency",
    "Status",
    "Invoice cost price",
    "Platform PP",
    "Invoice list price",
    "Platform list price",
    "Invoice SPP discount",
    "Platform SPP discount",
    "Expected SP",
    "Platform SP",
    "SP diff",
    "Failed checks",
    "Discounts applied",
    "Notes",
)


def _amount(amount: Decimal | None) -> float | str:
    if amount is None:
        return ""
    return float(amount)


def _discounts_applied(validation: AgreementValidation) -> str:
    expected = validation.expected
    if expected is None:
        return ""
    return "; ".join(
        f"{description}: {amount:.2f}" for description, amount in expected.discount_steps
    )


def _sales_price_diff(validation: AgreementValidation) -> Decimal | None:
    check = next((check for check in validation.checks if check.name == SALES_PRICE_CHECK), None)
    return check.diff if check else None


def describe_issues(validations: list[AgreementValidation]) -> str | None:
    """Teams message listing the agreements outside the tolerance, None when all match."""
    issues = [entry for entry in validations if entry.status != ValidationStatus.OK]
    if not issues:
        return None
    details = "\n\n".join(f"• {describe_validation(validation)}" for validation in issues)
    return (
        f"{len(issues)} agreement(s) do not match the AWS invoices "
        f"(see the Validation sheet of the billing report):\n\n{details}"
    )


def describe_validation(validation: AgreementValidation) -> str:
    """One line summary of a validation: agreement, status, failed checks and notes."""
    status = validation.status.value
    failed = ", ".join(
        f"{check.name} diff {check.diff:.2f} {validation.currency}"
        for check in validation.failed_checks
    )
    notes = " | ".join(validation.notes)
    parts = [f"{validation.agreement_id} ({validation.mpa}): {status}", failed, notes]
    return " - ".join(part for part in parts if part)


def build_validation_rows(validations: list[AgreementValidation]) -> list[list]:
    """One row per agreement, mismatches first."""
    ordered = sorted(validations, key=lambda entry: entry.status == ValidationStatus.OK)
    return [_row(validation) for validation in ordered]


def _row(validation: AgreementValidation) -> list:
    expected = validation.expected
    platform = validation.platform
    return [
        validation.authorization_id,
        validation.pma,
        validation.agreement_id,
        validation.mpa,
        validation.currency,
        validation.status.value,
        _amount(expected.cost_price if expected else None),
        _amount(platform.pp if platform else None),
        _amount(expected.list_price if expected else None),
        _amount(platform.list_price if platform else None),
        _amount(expected.spp_discount if expected else None),
        _amount(platform.spp_discount if platform else None),
        _amount(expected.sales_price if expected else None),
        _amount(platform.sp if platform else None),
        _amount(_sales_price_diff(validation)),
        ", ".join(check.name for check in validation.failed_checks),
        _discounts_applied(validation),
        " | ".join(validation.notes),
    ]
