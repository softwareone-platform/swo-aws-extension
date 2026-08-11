from decimal import Decimal

import pytest

from swo_aws_extension.flows.jobs.billing_journal.models.invoice import (
    InvoiceEntity,
    OrganizationInvoice,
    OrganizationInvoiceResult,
    RawInvoice,
)

PRIMARY_ENTITY_NAME = "AWS EMEA SARL"
PRIMARY_INVOICE_ID = "INV-001"
SECONDARY_ENTITY_NAME = "AWS Inc."
SECONDARY_INVOICE_ID = "INV-002"


def build_raw_invoice(
    account_id="MPA-123",
    invoice_id="INV-001",
    invoicing_entity="AWS Inc.",
    payment_currency="EUR",
    exchange_rate="0.95",
    discounts=None,
    bill_source_accounts=None,
):
    """Factory function to create RawInvoice instances for testing."""
    summary = {
        "AccountId": account_id,
        "InvoiceId": invoice_id,
        "Entity": {"InvoicingEntity": invoicing_entity},
        "BaseCurrencyAmount": {
            "CurrencyCode": "USD",
            "TotalAmount": "100.00",
        },
        "PaymentCurrencyAmount": {
            "CurrencyCode": payment_currency,
            "TotalAmount": "95.00",
            "CurrencyExchangeDetails": {"Rate": exchange_rate},
            "AmountBreakdown": {"SubTotalAmount": "105.00"},
        },
    }
    if discounts:
        summary["BaseCurrencyAmount"]["AmountBreakdown"] = {"Discounts": {"Breakdown": discounts}}
    if bill_source_accounts is not None:
        summary["BillSourceAccounts"] = bill_source_accounts
    return RawInvoice(summary)


@pytest.mark.parametrize(
    ("invoice", "expected"),
    [
        (build_raw_invoice(invoicing_entity="AWS Inc."), "AWS Inc.:AWS"),
        (RawInvoice({}), ":AWS"),
    ],
)
def test_raw_invoice_entity_key(invoice, expected):
    result = invoice.entity_key  # act

    assert result == expected


@pytest.mark.parametrize(
    ("invoice", "expected"),
    [
        (build_raw_invoice(invoice_id="INV-001"), "INV-001"),
        (RawInvoice({}), ""),
    ],
)
def test_raw_invoice_invoice_id(invoice, expected):
    result = invoice.invoice_id  # act

    assert result == expected


@pytest.mark.parametrize(
    ("invoice", "base_currency", "payment_currency"),
    [
        (build_raw_invoice(), "USD", "EUR"),
        (RawInvoice({}), "", ""),
    ],
)
def test_raw_invoice_currency_codes(invoice, base_currency, payment_currency):
    result = (invoice.base_currency_code, invoice.payment_currency_code)  # act

    assert result == (base_currency, payment_currency)


def test_raw_invoice_exchange_rate_reads_payment_currency_exchange_details():
    invoice = build_raw_invoice(exchange_rate="0.87")

    result = invoice.exchange_rate

    assert result == Decimal("0.87")


def test_raw_invoice_exchange_rate_defaults_to_zero_when_missing():
    invoice = RawInvoice({"PaymentCurrencyAmount": {"CurrencyCode": "EUR"}})

    result = invoice.exchange_rate

    assert result == Decimal(0)


@pytest.mark.parametrize(
    ("invoice", "mpa_account", "expected"),
    [
        (build_raw_invoice(account_id="MPA-123"), "MPA-123", True),
        (build_raw_invoice(account_id="OTHER-456"), "MPA-123", False),
        (build_raw_invoice(bill_source_accounts=["MPA-123", "MPA-789"]), "MPA-123", True),
        (build_raw_invoice(bill_source_accounts=["OTHER-456"]), "MPA-123", False),
        (build_raw_invoice(bill_source_accounts=[]), "MPA-123", False),
    ],
)
def test_raw_invoice_belongs_to_mpa(invoice, mpa_account, expected):
    result = invoice.belongs_to_mpa(mpa_account)  # act

    assert result is expected


@pytest.mark.parametrize(
    ("discounts", "expected"),
    [
        ([{"Description": "Discount (AWS SPP Discount)"}], True),
        ([{"Description": "Some other discount"}], False),
        (None, False),
    ],
)
def test_raw_invoice_is_primary(discounts, expected):
    invoice = build_raw_invoice(discounts=discounts)

    result = invoice.is_primary  # act

    assert result is expected


@pytest.mark.parametrize(
    ("payment_currency", "exchange_rate", "currency", "expected"),
    [
        ("EUR", "0.95", "EUR", True),
        ("EUR", "0", "EUR", False),
        ("USD", "0.95", "EUR", False),
    ],
)
def test_raw_invoice_has_payment_rate(payment_currency, exchange_rate, currency, expected):
    invoice = build_raw_invoice(payment_currency=payment_currency, exchange_rate=exchange_rate)

    result = invoice.has_payment_rate(currency)  # act

    assert result is expected


def test_raw_invoice_amount_reads_currency_section():
    invoice = build_raw_invoice()

    result = invoice.amount("PaymentCurrencyAmount", "TotalAmount")

    assert result == Decimal("95.00")


def test_raw_invoice_amount_defaults_to_zero_when_missing():
    invoice = RawInvoice({})

    result = invoice.amount("PaymentCurrencyAmount", "TotalAmount")

    assert result == Decimal(0)


def test_raw_invoice_breakdown_amount_reads_amount_breakdown():
    invoice = build_raw_invoice()

    result = invoice.breakdown_amount("PaymentCurrencyAmount", "SubTotalAmount")

    assert result == Decimal("105.00")


def test_raw_invoice_breakdown_amount_defaults_to_zero_when_missing():
    invoice = RawInvoice({})

    result = invoice.breakdown_amount("PaymentCurrencyAmount", "SubTotalAmount")

    assert result == Decimal(0)


@pytest.fixture
def primary_entity():
    return InvoiceEntity(
        invoice_id=PRIMARY_INVOICE_ID,
        base_currency_code="USD",
        payment_currency_code="EUR",
        exchange_rate=Decimal("0.87"),
        primary=True,
    )


@pytest.fixture
def secondary_entity():
    return InvoiceEntity(
        invoice_id=SECONDARY_INVOICE_ID,
        base_currency_code="USD",
        payment_currency_code="USD",
        exchange_rate=Decimal("1.0"),
    )


def test_primary_entity_name_returns_name_when_primary_exists(
    primary_entity,
    secondary_entity,
):
    invoice = OrganizationInvoice(
        entities={
            SECONDARY_ENTITY_NAME: secondary_entity,
            PRIMARY_ENTITY_NAME: primary_entity,
        },
    )

    result = invoice.primary_entity_name

    assert result == PRIMARY_ENTITY_NAME


def test_primary_entity_name_returns_empty_when_no_primary(secondary_entity):
    invoice = OrganizationInvoice(
        entities={SECONDARY_ENTITY_NAME: secondary_entity},
    )

    result = invoice.primary_entity_name

    assert not result


def test_primary_entity_name_returns_empty_when_no_entities():
    invoice = OrganizationInvoice()

    result = invoice.primary_entity_name

    assert not result


def test_primary_invoice_id_returns_id_when_primary_exists(
    primary_entity,
    secondary_entity,
):
    invoice = OrganizationInvoice(
        entities={
            SECONDARY_ENTITY_NAME: secondary_entity,
            PRIMARY_ENTITY_NAME: primary_entity,
        },
    )

    result = invoice.primary_invoice_id

    assert result == PRIMARY_INVOICE_ID


def test_primary_invoice_id_returns_default_when_no_primary(secondary_entity):
    invoice = OrganizationInvoice(
        entities={SECONDARY_ENTITY_NAME: secondary_entity},
    )

    result = invoice.primary_invoice_id

    assert result == "invoice_id"


def test_primary_invoice_id_returns_default_when_no_entities():
    invoice = OrganizationInvoice()

    result = invoice.primary_invoice_id

    assert result == "invoice_id"


def test_invoice_ids_deduplicates_and_skips_missing_ids():
    result = OrganizationInvoiceResult(
        raw_data=[
            {"InvoiceId": PRIMARY_INVOICE_ID},
            {"InvoiceId": PRIMARY_INVOICE_ID},
            {"InvoiceId": SECONDARY_INVOICE_ID},
            {"InvoicingEntity": SECONDARY_ENTITY_NAME},
        ],
    )

    assert result.invoice_ids == {PRIMARY_INVOICE_ID, SECONDARY_INVOICE_ID}


def test_invoice_ids_returns_empty_when_no_raw_data():
    result = OrganizationInvoiceResult()

    assert result.invoice_ids == set()
