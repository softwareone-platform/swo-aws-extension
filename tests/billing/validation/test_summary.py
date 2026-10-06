from swo_aws_extension.billing.validation.summary import (
    describe_issues,
    describe_validation,
)
from tests.billing.validation.test_report import validations  # ruff: ignore[unused-import]


def test_describe_issues_counts_agreements_outside_tolerance_without_details(
    validations,  # ruff: ignore[redefined-while-unused]
):
    result = describe_issues(validations)

    assert result.startswith("3 of 4 agreement(s) need a review")
    assert "AGR-" not in result


def test_describe_issues_returns_none_when_everything_matches(validations):  # ruff: ignore[redefined-while-unused]
    result = describe_issues(validations[:1])

    assert result is None


def test_describe_validation_includes_likely_cause(validations):  # ruff: ignore[redefined-while-unused]
    result = describe_validation(validations[1])

    assert result.startswith("AGR-SMALL Kadensa (740386694475): MISMATCH - Sales price (SP)")
    assert "Cost Explorer reports less metered usage" in result
