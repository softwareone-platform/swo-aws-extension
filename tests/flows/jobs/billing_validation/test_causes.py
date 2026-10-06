from dataclasses import replace
from decimal import Decimal

import pytest

from swo_aws_extension.flows.jobs.billing_validation.calculator import ExpectedBillingCalculator
from swo_aws_extension.flows.jobs.billing_validation.causes import (
    COST_PRICE_MISMATCH,
    DISCOUNTS_NOT_EXPECTED,
    HANDSHAKE_NOT_APPROVED,
    LESS_USAGE,
    MORE_USAGE,
    NO_DISCOUNTS_IN_PLATFORM,
    UNEXPLAINED,
)
from swo_aws_extension.flows.jobs.billing_validation.results import ExpectedBilling
from swo_aws_extension.flows.jobs.billing_validation.validator import BillingValidator
from tests.flows.jobs.billing_validation.conftest import AGREEMENT_ID, MPA, PMA

BIG_DIFF = Decimal("500.00")
HUGE_DIFF = Decimal("900.00")


def _expected(mpa_invoices, discounts):
    return ExpectedBillingCalculator(Decimal("5.0")).calculate(
        ExpectedBilling(
            agreement_id=AGREEMENT_ID, mpa=MPA, pma=PMA, authorization_id="AUT", currency="USD"
        ),
        mpa_invoices,
        discounts,
        None,
    )


def test_cost_price_mismatch(mpa_invoices, discounts, platform_summary):
    expected = _expected(mpa_invoices, discounts)
    platform = replace(platform_summary, pp=platform_summary.pp + 100)

    result = BillingValidator().validate(expected, platform)

    assert result.likely_cause == COST_PRICE_MISMATCH


def test_platform_did_not_apply_discounts(mpa_invoices, discounts, platform_summary):
    expected = _expected(mpa_invoices, discounts)
    platform = replace(platform_summary, sp=expected.cost_price - expected.spp_discount)

    result = BillingValidator().validate(expected, platform)

    assert result.likely_cause == NO_DISCOUNTS_IN_PLATFORM


def test_handshake_not_approved(mpa_invoices, discounts, platform_summary):
    expected = _expected(mpa_invoices, replace(discounts, handshake_approved=False))
    platform = replace(platform_summary, sp=platform_summary.sp - BIG_DIFF)

    result = BillingValidator().validate(expected, platform)

    assert result.likely_cause == HANDSHAKE_NOT_APPROVED


def test_platform_applied_unexpected_discounts(mpa_invoices, discounts, platform_summary):
    expected = _expected(mpa_invoices, replace(discounts, service_discount=Decimal(0)))
    platform = replace(platform_summary, sp=expected.sales_price + expected.spp_discount)

    result = BillingValidator().validate(expected, platform)

    assert result.likely_cause == DISCOUNTS_NOT_EXPECTED


@pytest.mark.parametrize(
    ("delta", "cause"),
    [
        (Decimal("-38.40"), LESS_USAGE),
        (Decimal("38.40"), MORE_USAGE),
        (-HUGE_DIFF, UNEXPLAINED),
    ],
)
def test_usage_differences(mpa_invoices, discounts, platform_summary, delta, cause):
    expected = _expected(mpa_invoices, discounts)
    platform = replace(platform_summary, sp=platform_summary.sp + delta)

    result = BillingValidator().validate(expected, platform)

    assert result.likely_cause == cause


def test_agreement_not_found(mpa_invoices, platform_summary):
    expected = _expected(mpa_invoices, None)
    platform = replace(platform_summary, sp=platform_summary.sp + BIG_DIFF)

    result = BillingValidator().validate(expected, platform)

    assert result.likely_cause.startswith("Agreement not found in the platform")
