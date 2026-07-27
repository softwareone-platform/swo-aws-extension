from decimal import Decimal

import pytest

from swo_aws_extension.billing.generators.invoice_utils import (
    belongs_to_mpa,
    get_invoice_rate,
    is_primary_invoice,
    merge_invoice_ids,
)


def build_invoice(
    account_id="MPA-123",
    invoice_id="INV-001",
    invoicing_entity="AWS Inc.",
    base_currency="USD",
    base_total="100.00",
    base_total_before_tax="90.00",
    payment_currency="EUR",
    payment_total="95.00",
    payment_total_before_tax="85.00",
    payment_subtotal="105.00",
    exchange_rate="0.95",
    discounts=None,
    bill_source_accounts=None,
):
    """Factory function to create invoice dictionaries for testing."""
    invoice = {
        "AccountId": account_id,
        "InvoiceId": invoice_id,
        "Entity": {"InvoicingEntity": invoicing_entity},
        "BaseCurrencyAmount": {
            "CurrencyCode": base_currency,
            "TotalAmount": base_total,
            "TotalAmountBeforeTax": base_total_before_tax,
        },
        "PaymentCurrencyAmount": {
            "CurrencyCode": payment_currency,
            "TotalAmount": payment_total,
            "TotalAmountBeforeTax": payment_total_before_tax,
            "CurrencyExchangeDetails": {"Rate": exchange_rate},
            "AmountBreakdown": {"SubTotalAmount": payment_subtotal},
        },
    }
    if discounts:
        invoice["BaseCurrencyAmount"]["AmountBreakdown"] = {"Discounts": {"Breakdown": discounts}}
    if bill_source_accounts is not None:
        invoice["BillSourceAccounts"] = bill_source_accounts
    return invoice


def test_get_invoice_rate_reads_payment_currency_exchange_details():
    invoice = build_invoice(exchange_rate="0.87")

    result = get_invoice_rate(invoice)

    assert result == Decimal("0.87")


def test_get_invoice_rate_defaults_to_zero_when_missing():
    invoice = {"PaymentCurrencyAmount": {"CurrencyCode": "EUR"}}

    result = get_invoice_rate(invoice)

    assert result == Decimal(0)


@pytest.mark.parametrize(
    ("invoice", "mpa_account", "expected"),
    [
        (build_invoice(account_id="MPA-123"), "MPA-123", True),
        (build_invoice(account_id="OTHER-456"), "MPA-123", False),
        (build_invoice(bill_source_accounts=["MPA-123", "MPA-789"]), "MPA-123", True),
        (build_invoice(bill_source_accounts=["OTHER-456"]), "MPA-123", False),
        (build_invoice(bill_source_accounts=[]), "MPA-123", False),
    ],
)
def test_belongs_to_mpa(invoice, mpa_account, expected):
    result = belongs_to_mpa(invoice, mpa_account)  # act

    assert result is expected


@pytest.mark.parametrize(
    ("discounts", "expected"),
    [
        ([{"Description": "Discount (AWS SPP Discount)"}], True),
        ([{"Description": "Some other discount"}], False),
        (None, False),
    ],
)
def test_is_primary_invoice(discounts, expected):
    invoice = build_invoice(discounts=discounts)

    result = is_primary_invoice(invoice)  # act

    assert result is expected


@pytest.mark.parametrize(
    ("existing_id", "new_id", "expected"),
    [
        ("2609293185", "", "2609293185"),
        ("2609293185", "SGIN26-350441", "-3185,-0441"),
        ("-3185,-0441", "EUINPL26-355205", "-3185,-0441,-5205"),
        ("-3185,-0441,-5205", "NEXT26-000002", "-3185,-0441,-5205,.."),
        ("-3185,-0441,-5205,..", "NEXT26-000003", "-3185,-0441,-5205,.."),
    ],
)
def test_merge_invoice_ids(existing_id, new_id, expected):
    result = merge_invoice_ids(existing_id, new_id)  # act

    assert result == expected
