from dataclasses import replace
from decimal import Decimal

import pytest

from swo_aws_extension.flows.jobs.billing_validation.calculator import ExpectedBillingCalculator
from swo_aws_extension.flows.jobs.billing_validation.models import AgreementNames
from swo_aws_extension.flows.jobs.billing_validation.report import (
    VALIDATION_HEADERS,
    build_validation_rows,
)
from swo_aws_extension.flows.jobs.billing_validation.results import ExpectedBilling
from swo_aws_extension.flows.jobs.billing_validation.validator import BillingValidator
from tests.flows.jobs.billing_validation.conftest import AGREEMENT_ID, MPA, PMA

SMALL_DIFF = 2
ONE_CENT = 0.01
SERVICE_DISCOUNT_PCT = 62.5
SERVICE_DISCOUNT_AMOUNT = -883.9


@pytest.fixture
def validations(mpa_invoices, discounts, platform_summary):
    expected = ExpectedBillingCalculator(Decimal("5.0")).calculate(
        ExpectedBilling(
            agreement_id=AGREEMENT_ID,
            mpa=MPA,
            pma=PMA,
            authorization_id="AUT",
            currency="USD",
            names=AgreementNames(
                agreement_name="Kadensa", client_name="Kadensa Ltd", authorization_name="SWO UK"
            ),
        ),
        mpa_invoices,
        discounts,
        None,
    )
    validator = BillingValidator()
    wrong = replace(platform_summary, agreement_id="AGR-WRONG", sp=Decimal(1))
    small = replace(platform_summary, agreement_id="AGR-SMALL", sp=platform_summary.sp - SMALL_DIFF)
    return [
        validator.validate(expected, platform_summary),
        validator.validate(replace(expected, agreement_id="AGR-SMALL"), small),
        validator.validate(replace(expected, agreement_id="AGR-WRONG"), wrong),
        validator.missing_invoices(replace(platform_summary, agreement_id="AGR-NOINV")),
    ]


def test_build_validation_rows_puts_issues_first_largest_diff_on_top(validations):
    result = build_validation_rows(validations)

    agreement_column = VALIDATION_HEADERS.index("Agreement ID")
    assert [row[agreement_column] for row in result] == [
        "AGR-WRONG",
        "AGR-SMALL",
        "AGR-NOINV",
        AGREEMENT_ID,
    ]
    assert all(len(row) == len(VALIDATION_HEADERS) for row in result)


def test_build_validation_rows_contains_expected_and_platform_amounts(validations):
    result = build_validation_rows(validations)

    ok_row = dict(zip(VALIDATION_HEADERS, result[-1], strict=True))
    assert ok_row["Status"] == "OK"
    assert ok_row["Expected SP"] == pytest.approx(float("17046.21"))
    assert ok_row["Platform SP"] == pytest.approx(float("17046.2095703969"))


def test_build_validation_rows_contains_discount_columns(validations):
    result = build_validation_rows(validations)

    ok_row = dict(zip(VALIDATION_HEADERS, result[-1], strict=True))
    assert ok_row["Service discount %"] == pytest.approx(SERVICE_DISCOUNT_PCT)
    assert ok_row["Service discount"] == pytest.approx(SERVICE_DISCOUNT_AMOUNT)
    assert ok_row["Total discounts"] == pytest.approx(SERVICE_DISCOUNT_AMOUNT)
    assert ok_row["Handshake approved"] == "yes"
    assert not ok_row["Support discount %"]


def test_build_validation_rows_contains_names_invoices_and_exchange_rate(validations):
    result = build_validation_rows(validations)

    ok_row = dict(zip(VALIDATION_HEADERS, result[-1], strict=True))
    assert ok_row["Authorization"] == "SWO UK"
    assert ok_row["Client"] == "Kadensa Ltd"
    assert ok_row["Agreement"] == "Kadensa"
    assert (ok_row["Invoices"], ok_row["Exchange rate source"]) == (
        "2847784289",
        "none (base currency)",
    )
    assert ok_row["Exchange rate"] == pytest.approx(1)


def test_build_validation_rows_mismatch_has_likely_cause(validations):
    result = build_validation_rows(validations)

    small_row = dict(zip(VALIDATION_HEADERS, result[1], strict=True))
    assert small_row["Status"] == "MISMATCH"
    assert small_row["SP diff"] == pytest.approx(-SMALL_DIFF, abs=ONE_CENT)
    assert small_row["Likely cause"].startswith("Cost Explorer reports less metered usage")


def test_build_validation_rows_missing_invoices_has_empty_expected_cells(validations):
    result = build_validation_rows(validations)

    missing_row = dict(zip(VALIDATION_HEADERS, result[2], strict=True))
    assert missing_row["Status"] == "MISSING_INVOICES"
    assert not missing_row["Invoice cost price"]
    assert not missing_row["Tolerance"]
    assert not missing_row["Handshake approved"]
    assert missing_row["Likely cause"] == "No AWS invoices found for the MPA account."
