from swo_aws_extension.billing.validation.summary import (
    describe_issues,
    describe_validation,
    summarize,
)
from tests.billing.validation.conftest import AGREEMENT_ID
from tests.billing.validation.test_report import validations  # ruff: ignore[unused-import]


def test_describe_issues_lists_only_agreements_outside_tolerance(validations):  # ruff: ignore[redefined-while-unused]
    result = describe_issues(validations)

    assert result.startswith(
        "4 agreement(s) validated, 3 outside the tolerance, 0 without discounts configured."
    )
    assert "SP difference per currency: -17047.21 USD" in result
    assert "AGR-WRONG Kadensa (740386694475): MISMATCH - Sales price (SP) diff" in result
    assert f"{AGREEMENT_ID} Kadensa" not in result


def test_describe_issues_returns_none_when_everything_matches(validations):  # ruff: ignore[redefined-while-unused]
    result = describe_issues(validations[:1])

    assert result is None


def test_summarize_counts_agreements_without_discounts(validations):  # ruff: ignore[redefined-while-unused]
    validations[0].expected.steps.clear()

    result = summarize(validations[:1])

    assert result.startswith("1 agreement(s) validated, 0 outside the tolerance, 1 without")
    assert "SP difference per currency: none" in result


def test_describe_validation_includes_likely_cause(validations):  # ruff: ignore[redefined-while-unused]
    result = describe_validation(validations[1])

    assert result.startswith("AGR-SMALL Kadensa (740386694475): MISMATCH - Sales price (SP)")
    assert "Cost Explorer reports less metered usage" in result
