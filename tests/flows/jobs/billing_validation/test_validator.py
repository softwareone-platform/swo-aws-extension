from dataclasses import replace
from decimal import Decimal

import pytest

from swo_aws_extension.flows.jobs.billing_validation.calculator import ExpectedBillingCalculator
from swo_aws_extension.flows.jobs.billing_validation.results import (
    ExpectedBilling,
    ValidationStatus,
)
from swo_aws_extension.flows.jobs.billing_validation.validator import BillingValidator
from tests.flows.jobs.billing_validation.conftest import AGREEMENT_ID, MPA, PMA

IDR_RATE = Decimal("17924.76")


@pytest.fixture
def expected(mpa_invoices, discounts):
    billing = ExpectedBilling(
        agreement_id=AGREEMENT_ID, mpa=MPA, pma=PMA, authorization_id="AUT", currency="USD"
    )
    return ExpectedBillingCalculator(Decimal("5.0")).calculate(
        billing, mpa_invoices, discounts, None
    )


def test_validate_within_tolerance_is_ok(expected, platform_summary):
    result = BillingValidator(Decimal("0.05")).validate(expected, platform_summary)

    assert result.status == ValidationStatus.OK
    assert [check.name for check in result.checks] == [
        "Cost price (PP)",
        "List price",
        "SPP discount",
        "Sales price (SP)",
        "SP from markup (PP * (1 + markup))",
    ]


def test_validate_flags_sales_price_outside_tolerance(expected, platform_summary):
    sales_price = platform_summary.sp - Decimal("1.03")
    platform = replace(
        platform_summary, sp=sales_price, markup=sales_price / platform_summary.pp - 1
    )

    result = BillingValidator(Decimal("0.05")).validate(expected, platform)

    assert result.status == ValidationStatus.MISMATCH
    assert [check.name for check in result.failed_checks] == ["Sales price (SP)"]
    assert any("journal total does not" in note for note in result.notes)


def test_validate_scales_tolerance_with_exchange_rate(expected, platform_summary):
    for line in expected.invoices.lines:
        line.exchange_rate = IDR_RATE
    platform = replace(platform_summary, sp=platform_summary.sp + Decimal("60.00"))

    result = BillingValidator(Decimal("0.05")).validate(expected, platform)

    assert result.status == ValidationStatus.OK


def test_validate_without_platform_row(expected):
    result = BillingValidator().validate(expected, None)

    assert result.status == ValidationStatus.MISSING_IN_PLATFORM
    assert result.checks == []


def test_missing_invoices(platform_summary):
    result = BillingValidator().missing_invoices(platform_summary)

    assert result.status == ValidationStatus.MISSING_INVOICES
    assert result.agreement_id == AGREEMENT_ID
