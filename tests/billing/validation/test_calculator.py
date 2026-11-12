from decimal import Decimal

import pytest

from swo_aws_extension.billing.validation.calculator import ExpectedBillingCalculator
from swo_aws_extension.billing.validation.models import (
    AgreementDiscounts,
    MpaInvoices,
    ServiceSplit,
)
from swo_aws_extension.billing.validation.results import DiscountKind, ExpectedBilling
from swo_aws_extension.constants import ServiceDiscountTypeEnum, SupportTypesEnum
from tests.billing.validation.conftest import (
    AGREEMENT_ID,
    MPA,
    PMA,
    build_invoice_line,
)

# cost price + whole SPP discount of the KADENSA fixture: 16515.87 + 1414.24
SPP_KEPT_SALES_PRICE = Decimal("17930.11")


@pytest.fixture
def calculator():
    return ExpectedBillingCalculator(Decimal("5.0"))


@pytest.fixture
def expected():
    return ExpectedBilling(
        agreement_id=AGREEMENT_ID,
        mpa=MPA,
        pma=PMA,
        authorization_id="AUT-7443-3939",
        currency="USD",
    )


def test_calculate_passes_share_of_spp_discount_to_customer(
    calculator, expected, mpa_invoices, discounts
):
    result = calculator.calculate(expected, mpa_invoices, discounts, None)

    # manual sheet: net usage minus the 62.5% share of the SPP discount given to the customer
    assert result.cost_price == Decimal("16515.87")
    assert result.sales_price == Decimal("17046.21")
    assert result.markup.quantize(Decimal("0.0001")) == Decimal("0.0321")


def test_calculate_without_agreement_keeps_whole_spp_discount(calculator, expected, mpa_invoices):
    result = calculator.calculate(expected, mpa_invoices, None, None)

    assert result.sales_price == SPP_KEPT_SALES_PRICE
    assert "Agreement not found" in result.notes[0]


def test_calculate_applies_discounts_when_handshake_not_approved(
    calculator, expected, mpa_invoices
):
    discounts = AgreementDiscounts(
        agreement_id=AGREEMENT_ID,
        mpa=MPA,
        handshake_approved=False,
        service_discount=Decimal("62.5"),
    )

    result = calculator.calculate(expected, mpa_invoices, discounts, None)

    assert result.sales_price == Decimal("17046.21")


def test_calculate_zero_aws_invoice_returns_spp_to_customer(calculator, expected, discounts):
    invoices = MpaInvoices(
        mpa=MPA,
        currency="USD",
        lines=[
            build_invoice_line(charges="1460.45", spp="-105.92", cost="0"),
            build_invoice_line(
                charges="50.00", spp="0", cost="50.00", billing_entity="AWS_MARKETPLACE"
            ),
        ],
    )

    result = calculator.calculate(expected, invoices, discounts, None)

    assert result.sales_price == Decimal("50.00")
    assert "returned to the customer" in result.notes[0]


def test_calculate_zero_principal_invoice_with_one_time_purchase(calculator, expected, discounts):
    # Tan Long: usage invoice fully covered by credits plus a 9300 USD Countdown purchase
    invoices = MpaInvoices(
        mpa=MPA,
        currency="USD",
        lines=[
            build_invoice_line(charges="9300.00", spp="0", cost="9300.00", has_spp_breakdown=False),
            build_invoice_line(charges="1662.77", spp="-199.55", cost="0"),
        ],
    )

    result = calculator.calculate(expected, invoices, discounts, None)

    assert result.sales_price == Decimal("9300.00")
    assert "principal AWS invoice is 0" in result.notes[0]


def test_calculate_excludes_support_spp_from_service_discount(
    calculator, expected, mpa_invoices, discounts
):
    split = ServiceSplit(
        resold_support_charge=Decimal("100.00"), resold_support_spp=Decimal("-7.00")
    )

    result = calculator.calculate(expected, mpa_invoices, discounts, split)

    # the SPP discount on support is kept by SWO, so the service discount excludes it
    assert result.sales_price == Decimal("17050.585")


def test_calculate_applies_support_discount_on_resold_support(calculator, expected, mpa_invoices):
    discounts = AgreementDiscounts(
        agreement_id=AGREEMENT_ID,
        mpa=MPA,
        support_type=SupportTypesEnum.AWS_RESOLD_SUPPORT,
        support_discount=Decimal("71.0"),
    )
    split = ServiceSplit(
        resold_support_charge=Decimal("295.35"), resold_support_spp=Decimal("-20.65")
    )

    result = calculator.calculate(expected, mpa_invoices, discounts, split)

    assert result.sales_price == SPP_KEPT_SALES_PRICE - Decimal("14.6615")


def test_calculate_usage_amount_discount_type_uses_discount_base(
    calculator, expected, mpa_invoices
):
    discounts = AgreementDiscounts(
        agreement_id=AGREEMENT_ID,
        mpa=MPA,
        service_discount=Decimal("5.0"),
        service_discount_type=ServiceDiscountTypeEnum.USAGE_AMOUNT,
    )
    # the usage base carries the recurring fees, as in the journal
    split = ServiceSplit(usage_base=Decimal("1500.00"))

    result = calculator.calculate(expected, mpa_invoices, discounts, split)

    assert result.sales_price == SPP_KEPT_SALES_PRICE - Decimal("75.00")


def test_calculate_usage_amount_discount_type_skips_nonpositive_usage_base(
    calculator, expected, mpa_invoices
):
    discounts = AgreementDiscounts(
        agreement_id=AGREEMENT_ID,
        mpa=MPA,
        service_discount=Decimal("5.0"),
        service_discount_type=ServiceDiscountTypeEnum.USAGE_AMOUNT,
    )
    # the bundled discount exceeds the usage: the journal emits no discount line
    split = ServiceSplit(usage_base=Decimal("-10.00"))

    result = calculator.calculate(expected, mpa_invoices, discounts, split)

    assert result.sales_price == SPP_KEPT_SALES_PRICE
    assert result.steps == []


def test_calculate_pls_skips_charge_and_discount_on_nonpositive_usage_base(
    calculator, expected, mpa_invoices
):
    discounts = AgreementDiscounts(
        agreement_id=AGREEMENT_ID,
        mpa=MPA,
        support_type=SupportTypesEnum.PARTNER_LED_SUPPORT,
        pls_discount=Decimal("10.0"),
    )
    split = ServiceSplit(
        enterprise_support_charge=Decimal("200.00"),
        usage_base=Decimal("-10.00"),
    )

    result = calculator.calculate(expected, mpa_invoices, discounts, split)

    # only the AWS enterprise support is removed, as the journal generates no PLS charge
    assert result.sales_price == SPP_KEPT_SALES_PRICE - Decimal("200.00")
    assert [step.kind for step in result.steps] == [DiscountKind.PLS_SUPPORT_REMOVED]


def test_calculate_pls_applies_on_usage_base(calculator, expected, mpa_invoices):
    discounts = AgreementDiscounts(
        agreement_id=AGREEMENT_ID,
        mpa=MPA,
        support_type=SupportTypesEnum.PARTNER_LED_SUPPORT,
        pls_discount=Decimal("10.0"),
    )
    split = ServiceSplit(
        enterprise_support_charge=Decimal("200.00"),
        usage_base=Decimal("1500.00"),
    )

    result = calculator.calculate(expected, mpa_invoices, discounts, split)

    # minus the AWS enterprise support (200), plus 5% of usage and recurring fees (75)
    # and minus 10% of that PLS charge (7.5)
    assert result.sales_price == SPP_KEPT_SALES_PRICE - Decimal("132.50")


def test_calculate_partner_led_support_replaces_enterprise_support(
    calculator, expected, service_split
):
    invoices = MpaInvoices(
        mpa=MPA,
        currency="USD",
        lines=[build_invoice_line(charges="14349.63", spp="-1761.52", cost="12586.88")],
    )
    discounts = AgreementDiscounts(
        agreement_id=AGREEMENT_ID,
        mpa=MPA,
        support_type=SupportTypesEnum.PARTNER_LED_SUPPORT,
        pls_discount=Decimal("10.0"),
    )

    result = calculator.calculate(expected, invoices, discounts, service_split)

    # cost plus SPP (14348.40), minus the AWS enterprise support (206.11),
    # plus 5% of the usage base (707.115) and minus 10% of that PLS charge (70.7115)
    assert result.sales_price == Decimal("14778.6935")
    assert result.notes == []


def test_calculate_reports_pls_mismatch(
    calculator, expected, mpa_invoices, discounts, service_split
):
    result = calculator.calculate(expected, mpa_invoices, discounts, service_split)

    # 16515.87 + 1414.24 - 62.5% of the SPP discount on usage (1414.24 - 82.45)
    assert any("PLS mismatch" in note for note in result.notes)
    assert result.sales_price == Decimal("17097.74125")
