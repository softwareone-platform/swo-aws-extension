from swo_aws_extension.flows.jobs.billing_validation.summary import (
    describe_issues,
    describe_validation,
)
from tests.flows.jobs.billing_validation.test_report import validations  # noqa: F401


def test_describe_issues_counts_agreements_outside_tolerance_without_details(
    validations,  # noqa: F811
):
    result = describe_issues(validations)

    assert result.startswith("3 of 4 agreement(s) need a review")
    assert "AGR-" not in result


def test_describe_issues_returns_none_when_everything_matches(validations):  # noqa: F811
    result = describe_issues(validations[:1])

    assert result is None


def test_describe_validation_includes_likely_cause(validations):  # noqa: F811
    result = describe_validation(validations[1])

    assert result.startswith("AGR-SMALL Kadensa (740386694475): MISMATCH - Sales price (SP)")
    assert "Cost Explorer reports less metered usage" in result
