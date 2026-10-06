from dataclasses import replace
from decimal import Decimal

import pytest

from swo_aws_extension.billing.validation.calculator import ExpectedBillingCalculator
from swo_aws_extension.billing.validation.report import (
    VALIDATION_HEADERS,
    build_validation_rows,
    describe_issues,
)
from swo_aws_extension.billing.validation.results import ExpectedBilling
from swo_aws_extension.billing.validation.validator import BillingValidator
from tests.billing.validation.conftest import AGREEMENT_ID, MPA, PMA


@pytest.fixture
def validations(mpa_invoices, discounts, platform_summary):
    expected = ExpectedBillingCalculator(Decimal("5.0")).calculate(
        ExpectedBilling(
            agreement_id=AGREEMENT_ID, mpa=MPA, pma=PMA, authorization_id="AUT", currency="USD"
        ),
        mpa_invoices,
        discounts,
        None,
    )
    validator = BillingValidator()
    wrong = replace(platform_summary, agreement_id="AGR-WRONG", sp=Decimal(1))
    return [
        validator.validate(expected, platform_summary),
        validator.validate(replace(expected, agreement_id="AGR-WRONG"), wrong),
        validator.missing_invoices(replace(platform_summary, agreement_id="AGR-NOINV")),
    ]


def test_build_validation_rows_puts_issues_first(validations):
    result = build_validation_rows(validations)

    agreement_column = VALIDATION_HEADERS.index("Agreement ID")
    assert [row[agreement_column] for row in result] == ["AGR-WRONG", "AGR-NOINV", AGREEMENT_ID]
    assert all(len(row) == len(VALIDATION_HEADERS) for row in result)


def test_build_validation_rows_contains_expected_and_platform_amounts(validations):
    result = build_validation_rows(validations)

    ok_row = dict(zip(VALIDATION_HEADERS, result[-1], strict=True))
    assert ok_row["Status"] == "OK"
    assert ok_row["Expected SP"] == pytest.approx(float("17046.21"))
    assert ok_row["Platform SP"] == pytest.approx(float("17046.2095703969"))
    assert ok_row["Discounts applied"].startswith(
        "SWO service discount 62.5% of SPP discount on usage: -883.90"
    )


def test_build_validation_rows_missing_invoices_has_empty_expected_cells(validations):
    result = build_validation_rows(validations)

    missing_row = dict(zip(VALIDATION_HEADERS, result[1], strict=True))
    assert missing_row["Status"] == "MISSING_INVOICES"
    assert not missing_row["Invoice cost price"]
    assert not missing_row["Tolerance"]
    assert missing_row["Notes"] == "No AWS invoices found for the MPA account."


def test_describe_issues_lists_only_agreements_outside_tolerance(validations):
    result = describe_issues(validations)

    assert result.startswith("2 agreement(s) do not match the AWS invoices")
    assert "AGR-WRONG (740386694475): MISMATCH - Sales price (SP) diff" in result
    assert AGREEMENT_ID not in result


def test_describe_issues_returns_none_when_everything_matches(validations):
    result = describe_issues(validations[:1])

    assert result is None
