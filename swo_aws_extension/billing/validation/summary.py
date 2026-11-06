"""Teams and log summaries of the billing validation."""

from swo_aws_extension.billing.validation.results import (
    AgreementValidation,
    ValidationStatus,
)


def describe_issues(validations: list[AgreementValidation]) -> str | None:
    """Short Teams message: how many agreements need a review, without details.

    Returns None when every agreement matches.
    """
    issues = [entry for entry in validations if entry.status != ValidationStatus.OK]
    if not issues:
        return None
    return (
        f"{len(issues)} of {len(validations)} agreement(s) need a review: the billing "
        "journal does not match the AWS invoices or the agreement discounts. "
        "See the Validation sheet of the billing report."
    )


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
