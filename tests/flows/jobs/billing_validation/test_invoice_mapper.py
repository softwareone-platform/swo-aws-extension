from decimal import Decimal
from types import MappingProxyType

from swo_aws_extension.flows.jobs.billing_validation.invoice_mapper import InvoiceMapper
from tests.flows.jobs.billing_validation.conftest import MPA, build_invoice_summary

EUR_PAYMENT = MappingProxyType({
    "CurrencyCode": "EUR",
    "TotalAmount": "100.00",
    "TotalAmountBeforeTax": "90.00",
    "CurrencyExchangeDetails": {"Rate": "0.9"},
    "AmountBreakdown": {
        "SubTotalAmount": "99.00",
        "Discounts": {
            "Breakdown": [{"Description": "Discount (AWS SPP Discount)", "Amount": "-9.00"}]
        },
    },
})


def test_for_mpa_maps_usd_invoice_totals():
    mapper = InvoiceMapper([build_invoice_summary()], "USD")

    result = mapper.for_mpa(MPA)

    assert result.cost_price == Decimal("16515.87")
    assert result.list_price == Decimal("19295.13")
    assert result.spp_discount == Decimal("-1414.24")
    assert result.exchange_rate == Decimal(1)


def test_for_mpa_derives_other_adjustments_from_totals():
    mapper = InvoiceMapper([build_invoice_summary()], "USD")

    result = mapper.for_mpa(MPA)

    assert result.lines[0].other_adjustments == Decimal("-1365.02")
    assert result.lines[0].category == "Usage"


def test_for_mpa_filters_by_bill_source_account_and_marks_marketplace():
    summaries = [
        build_invoice_summary(invoice_id="2847743341", billing_entity="AWS_MARKETPLACE"),
        build_invoice_summary(invoice_id="OTHER", mpa="999999999999"),
    ]

    result = InvoiceMapper(summaries, "USD").for_mpa(MPA)

    assert [line.invoice_id for line in result.lines] == ["2847743341"]
    assert result.lines[0].category == "AWS Marketplace"


def test_for_mpa_uses_payment_currency_when_reported():
    summaries = [build_invoice_summary(payment=dict(EUR_PAYMENT))]

    result = InvoiceMapper(summaries, "EUR").for_mpa(MPA)

    line = result.lines[0]
    assert (line.cost, line.charges, line.spp_discount) == (
        Decimal("90.00"),
        Decimal("99.00"),
        Decimal("-9.00"),
    )
    assert line.tax == Decimal("10.00")
    assert line.exchange_rate == Decimal("0.9")


def test_for_mpa_converts_base_amounts_with_sibling_rate():
    summaries = [
        build_invoice_summary(invoice_id="EU-1", payment=dict(EUR_PAYMENT)),
        build_invoice_summary(
            invoice_id="MP-1",
            billing_entity="AWS_MARKETPLACE",
            subtotal="100.00",
            spp="0",
            total_before_tax="100.00",
            total="100.00",
        ),
    ]

    result = InvoiceMapper(summaries, "EUR").for_mpa(MPA)

    marketplace = next(line for line in result.lines if line.invoice_id == "MP-1")
    assert marketplace.cost == Decimal("90.0")
    assert marketplace.exchange_rate == Decimal("0.9")
    assert result.cost_price == Decimal("180.0")
