from decimal import Decimal

import pytest

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.flows.jobs.billing_journal.generators.invoice import (
    ExchangeRateResolver,
    InvoiceGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.invoice_utils import (
    MAX_INVOICE_ID_LENGTH,
)
from swo_aws_extension.flows.jobs.billing_journal.models.billing_period import BillingPeriod
from swo_aws_extension.flows.jobs.billing_journal.models.invoice import (
    OrganizationInvoiceResult,
    RawInvoice,
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


@pytest.fixture
def mock_aws_client(mocker):
    return mocker.MagicMock(spec=AWSClient)


@pytest.fixture
def billing_period():
    return BillingPeriod(start_date="2026-01-01", end_date="2026-02-01")


@pytest.fixture
def generator(mock_aws_client):
    return InvoiceGenerator(mock_aws_client)


def test_run_returns_organization_invoice_result(generator, mock_aws_client, billing_period):
    invoice = build_invoice(base_total="100.50")
    mock_aws_client.list_invoice_summaries_by_account_id.return_value = [invoice]

    result = generator.run("PMA-456", "MPA-123", billing_period, "EUR")

    assert isinstance(result, OrganizationInvoiceResult)
    assert len(result.raw_data) == 1


def test_run_filters_invoices_by_account_id(generator, mock_aws_client, billing_period):
    invoices = [
        build_invoice(account_id="MPA-123", invoice_id="INV-001"),
        build_invoice(account_id="OTHER-456", invoice_id="INV-002"),
    ]
    mock_aws_client.list_invoice_summaries_by_account_id.return_value = invoices

    result = generator.run("PMA-456", "MPA-123", billing_period, "EUR")

    assert len(result.raw_data) == 1
    assert result.raw_data[0]["InvoiceId"] == "INV-001"


def test_run_builds_invoice_entities(generator, mock_aws_client, billing_period):
    invoice = build_invoice()
    mock_aws_client.list_invoice_summaries_by_account_id.return_value = [invoice]

    result = generator.run("PMA-456", "MPA-123", billing_period, "EUR")

    assert "AWS Inc.:AWS" in result.invoice.entities
    entity = result.invoice.entities["AWS Inc.:AWS"]
    assert entity.invoice_id == "INV-001"
    assert entity.base_currency_code == "USD"
    assert entity.payment_currency_code == "EUR"
    assert entity.exchange_rate == Decimal("0.95")


def test_run_invoice_entity_has_correct_billing_entity(generator, mock_aws_client, billing_period):
    invoice = build_invoice()
    mock_aws_client.list_invoice_summaries_by_account_id.return_value = [invoice]

    result = generator.run("PMA-456", "MPA-123", billing_period, "EUR")  # act

    entity = result.invoice.entities["AWS Inc.:AWS"]
    assert entity.billing_entity == "AWS"


def test_run_merges_entities_and_calculates_totals(generator, mock_aws_client, billing_period):
    invoices = [
        build_invoice(invoice_id="2609293185", base_total="100.00", payment_total="95.00"),
        build_invoice(
            invoice_id="SGIN26-350441",
            base_total="200.00",
            base_total_before_tax="180.00",
            payment_total="190.00",
            payment_total_before_tax="170.00",
        ),
    ]
    mock_aws_client.list_invoice_summaries_by_account_id.return_value = invoices

    result = generator.run("PMA-456", "MPA-123", billing_period, "EUR")

    entity = result.invoice.entities["AWS Inc.:AWS"]
    assert entity.invoice_id == "-3185,-0441"
    assert result.invoice.base_total_amount == Decimal("300.00")
    assert result.invoice.base_total_amount_before_tax == Decimal("270.00")
    assert result.invoice.payment_currency_total_amount == Decimal("285.00")
    assert result.invoice.payment_currency_total_amount_before_tax == Decimal("255.00")


def test_run_sums_payment_currency_subtotal_amount_across_invoices(
    generator, mock_aws_client, billing_period
):
    invoices = [
        build_invoice(invoice_id="INV-1", payment_subtotal="100.00"),
        build_invoice(invoice_id="INV-2", payment_subtotal="50.00"),
    ]
    mock_aws_client.list_invoice_summaries_by_account_id.return_value = invoices

    result = generator.run("PMA-456", "MPA-123", billing_period, "EUR")

    assert result.invoice.payment_currency_subtotal_amount == Decimal("150.00")


def test_run_converts_base_amounts_when_invoice_has_no_exchange_rate(
    generator, mock_aws_client, billing_period
):
    with_rate = build_invoice(
        invoice_id="INV-1",
        base_total="100.00",
        base_total_before_tax="90.00",
        payment_total="95.00",
        payment_total_before_tax="85.50",
        payment_subtotal="105.00",
        exchange_rate="0.95",
    )
    without_rate = build_invoice(
        invoice_id="INV-2",
        base_total="200.00",
        base_total_before_tax="180.00",
    )
    without_rate.pop("PaymentCurrencyAmount")
    without_rate["BaseCurrencyAmount"]["AmountBreakdown"] = {"SubTotalAmount": "210.00"}
    mock_aws_client.list_invoice_summaries_by_account_id.return_value = [with_rate, without_rate]

    result = generator.run("PMA-456", "MPA-123", billing_period, "EUR")

    assert result.invoice.payment_currency_total_amount == Decimal("285.00")
    assert result.invoice.payment_currency_total_amount_before_tax == Decimal("256.50")
    assert result.invoice.payment_currency_subtotal_amount == Decimal("304.50")


def test_run_converts_base_amounts_with_highest_rate_when_entity_has_no_rate(
    generator, mock_aws_client, billing_period
):
    with_rate = build_invoice(
        invoice_id="INV-1",
        invoicing_entity="AWS Inc.",
        payment_total_before_tax="85.50",
        exchange_rate="0.95",
    )
    without_rate = build_invoice(
        invoice_id="INV-2",
        invoicing_entity="AWS EMEA",
        base_total_before_tax="180.00",
    )
    without_rate.pop("PaymentCurrencyAmount")
    mock_aws_client.list_invoice_summaries_by_account_id.return_value = [with_rate, without_rate]

    result = generator.run("PMA-456", "MPA-123", billing_period, "EUR")

    assert result.invoice.payment_currency_total_amount_before_tax == Decimal("256.50")


def test_run_keeps_base_amounts_when_no_invoice_has_exchange_rate(
    generator, mock_aws_client, billing_period
):
    invoice = build_invoice(invoice_id="INV-1", base_total_before_tax="90.00")
    invoice.pop("PaymentCurrencyAmount")
    mock_aws_client.list_invoice_summaries_by_account_id.return_value = [invoice]

    result = generator.run("PMA-456", "MPA-123", billing_period, "EUR")

    assert result.invoice.payment_currency_total_amount_before_tax == Decimal("90.00")


def test_run_handles_principal_invoice_amount_with_spp_discount(
    generator, mock_aws_client, billing_period
):
    invoice = build_invoice(
        base_total="-50.00",
        base_total_before_tax="-50.00",
        payment_total="-47.50",
        payment_total_before_tax="-47.50",
        discounts=[{"Description": "Discount (AWS SPP Discount)"}],
    )
    mock_aws_client.list_invoice_summaries_by_account_id.return_value = [invoice]

    result = generator.run("PMA-456", "MPA-123", billing_period, "EUR")

    assert result.invoice.principal_invoice_amount == Decimal("-50.00")


def test_run_handles_principal_invoice_amount_without_spp_discount(
    generator, mock_aws_client, billing_period
):
    invoice = build_invoice()
    mock_aws_client.list_invoice_summaries_by_account_id.return_value = [invoice]

    result = generator.run("PMA-456", "MPA-123", billing_period, "EUR")

    assert result.invoice.principal_invoice_amount is None


def test_run_handles_empty_invoices(generator, mock_aws_client, billing_period):
    mock_aws_client.list_invoice_summaries_by_account_id.return_value = []

    result = generator.run("PMA-456", "MPA-123", billing_period, "EUR")

    assert result.raw_data == []
    assert result.invoice.entities == {}
    assert result.invoice.base_total_amount == Decimal(0)


def test_run_filters_invoices_by_bill_source_accounts(generator, mock_aws_client, billing_period):
    invoices = [
        build_invoice(
            account_id="BUYER-001", invoice_id="INV-001", bill_source_accounts=["MPA-123"]
        ),
        build_invoice(
            account_id="BUYER-002", invoice_id="INV-002", bill_source_accounts=["OTHER-456"]
        ),
    ]
    mock_aws_client.list_invoice_summaries_by_account_id.return_value = invoices

    result = generator.run("PMA-456", "MPA-123", billing_period, "EUR")

    assert len(result.raw_data) == 1
    assert result.raw_data[0]["InvoiceId"] == "INV-001"


def test_run_filters_invoices_with_multiple_bill_source_accounts(
    generator, mock_aws_client, billing_period
):
    invoices = [
        build_invoice(
            account_id="BUYER-001",
            invoice_id="INV-001",
            bill_source_accounts=["MPA-123", "MPA-789"],
        ),
        build_invoice(
            account_id="BUYER-002",
            invoice_id="INV-002",
            bill_source_accounts=["OTHER-456"],
        ),
    ]
    mock_aws_client.list_invoice_summaries_by_account_id.return_value = invoices

    result = generator.run("PMA-456", "MPA-123", billing_period, "EUR")

    assert len(result.raw_data) == 1
    assert result.raw_data[0]["InvoiceId"] == "INV-001"


def test_run_excludes_invoices_with_empty_bill_source_accounts(
    generator, mock_aws_client, billing_period
):
    invoices = [
        build_invoice(account_id="MPA-123", invoice_id="INV-001", bill_source_accounts=[]),
    ]
    mock_aws_client.list_invoice_summaries_by_account_id.return_value = invoices

    result = generator.run("PMA-456", "MPA-123", billing_period, "EUR")

    assert result.raw_data == []


def test_run_falls_back_to_account_id_when_bill_source_accounts_absent(
    generator, mock_aws_client, billing_period
):
    invoices = [
        build_invoice(account_id="MPA-123", invoice_id="INV-001"),
        build_invoice(account_id="OTHER-456", invoice_id="INV-002"),
    ]
    mock_aws_client.list_invoice_summaries_by_account_id.return_value = invoices

    result = generator.run("PMA-456", "MPA-123", billing_period, "EUR")

    assert len(result.raw_data) == 1
    assert result.raw_data[0]["InvoiceId"] == "INV-001"


def test_merge_invoice_ids_result_never_exceeds_navision_limit(
    generator, mock_aws_client, billing_period
):
    invoice_count = 10
    invoice_id_template = "EUINPL26-3{0:05d}"
    invoices = [
        build_invoice(invoice_id=invoice_id_template.format(idx)) for idx in range(invoice_count)
    ]
    mock_aws_client.list_invoice_summaries_by_account_id.return_value = invoices

    result = generator.run("PMA-456", "MPA-123", billing_period, "EUR")  # act

    entity = result.invoice.entities["AWS Inc.:AWS"]
    assert len(entity.invoice_id) <= MAX_INVOICE_ID_LENGTH
    assert entity.invoice_id.endswith(",..")


@pytest.mark.parametrize(
    ("entity", "currency", "expected"),
    [
        ("AWS Inc.", "EUR", Decimal("0.95")),
        ("Unknown Entity", "EUR", Decimal("0.95")),
        ("AWS Inc.", "GBP", Decimal(0)),
    ],
)
def test_exchange_rate_resolver_get_rate(entity, currency, expected):
    invoices = [
        RawInvoice(build_invoice(invoicing_entity="AWS Inc.", exchange_rate="0.90")),
        RawInvoice(build_invoice(invoicing_entity="AWS Inc.", exchange_rate="0.95")),
        RawInvoice(build_invoice(invoicing_entity="AWS EMEA", exchange_rate="0.92")),
    ]
    resolver = ExchangeRateResolver(invoices)

    result = resolver.get_rate(entity, currency)

    assert result == expected


def test_exchange_rate_resolver_get_rate_ignores_zero_entity_rates():
    invoices = [
        RawInvoice(build_invoice(invoicing_entity="AWS EMEA", exchange_rate="0")),
        RawInvoice(build_invoice(invoicing_entity="AWS Inc.", exchange_rate="0.95")),
    ]
    resolver = ExchangeRateResolver(invoices)

    result = resolver.get_rate("AWS EMEA", "EUR")

    assert result == Decimal("0.95")


def test_exchange_rate_resolver_get_payment_currency_uses_requested_currency_on_rate_ties():
    invoices = [
        RawInvoice(build_invoice(invoicing_entity="AWS UK", payment_currency="GBP")),
        RawInvoice(build_invoice(invoicing_entity="AWS EMEA", payment_currency="EUR")),
    ]
    resolver = ExchangeRateResolver(invoices)

    result = resolver.get_payment_currency(Decimal("0.95"), "EUR")

    assert result == "EUR"


@pytest.mark.parametrize(
    ("payment_currency", "expected_currency"),
    [
        ("EUR", "EUR"),
        (None, "USD"),
    ],
)
def test_exchange_rate_resolver_get_payment_currency_falls_back_on_zero_rate(
    payment_currency, expected_currency
):
    invoice = build_invoice(exchange_rate="0", payment_currency=payment_currency)
    if payment_currency is None:
        invoice.pop("PaymentCurrencyAmount")
    resolver = ExchangeRateResolver([RawInvoice(invoice)])

    result = resolver.get_payment_currency(Decimal(0), "GBP")

    assert result == expected_currency


def test_exchange_rate_resolver_get_payment_currency_defaults_to_usd_without_matching_rate():
    invoices = [RawInvoice(build_invoice(exchange_rate="0.95"))]
    resolver = ExchangeRateResolver(invoices)

    result = resolver.get_payment_currency(Decimal(0), "GBP")

    assert result == "USD"
