from decimal import Decimal

from swo_aws_extension.flows.jobs.billing_journal.invoice_details import InvoiceDetails


def test_amount_same_currency_unchanged(make_account_invoices):
    account_invoices = make_account_invoices()
    amount = Decimal("100.00")

    details = InvoiceDetails(
        item_external_id="item-123",
        service_name="EC2",
        amount=amount,
        account_id="111122223333",
        account_invoices=account_invoices,
        invoice_entity="entity-1",
        partner_discount=Decimal(0),
    )

    assert details.amount == amount


def test_amount_different_currency(make_account_invoices):
    account_invoices = make_account_invoices(
        payment_currency_code="EUR", base_currency_code="USD", exchange_rate=Decimal("0.92")
    )
    amount = Decimal("100.00")

    details = InvoiceDetails(
        item_external_id="item-123",
        service_name="S3",
        amount=amount,
        account_id="111122223333",
        account_invoices=account_invoices,
        invoice_entity="entity-1",
        partner_discount=Decimal(0),
    )

    assert details.amount == round(amount * Decimal("0.92"), 6)


def test_error_message_when_no_item_external_id(make_account_invoices):
    account_invoices = make_account_invoices(payment_currency_code="GBP", base_currency_code="GBP")

    details = InvoiceDetails(
        item_external_id=None,
        service_name="RDS",
        amount=Decimal("200.00"),
        account_id="444455556666",
        account_invoices=account_invoices,
        invoice_entity="entity-1",
        partner_discount=Decimal("-30.00"),
    )

    expected_discount = (abs(Decimal("-30.00")) / Decimal("200.00")) * 100
    expected = (
        f"444455556666 - Service RDS with amount {Decimal('200.00')} GBP and discount "
        f"{expected_discount} did not match any subscription item."
    )
    assert details.error == expected


def test_public_attributes_match_expected_dict(make_account_invoices):
    account_invoices = make_account_invoices(
        invoice_id="INV-123", payment_currency_code="USD", base_currency_code="USD"
    )
    amount = Decimal("150.50")

    details = InvoiceDetails(
        item_external_id="ext-2",
        service_name="Athena",
        amount=amount,
        account_id="123456789012",
        account_invoices=account_invoices,
        invoice_entity="entity-1",
        partner_discount=Decimal(0),
    )

    expected = {
        "service_name": "Athena",
        "account_id": "123456789012",
        "invoice_entity": "entity-1",
        "invoice_id": "INV-123",
        "amount": amount,
        "error": None,
    }
    actual = {
        "service_name": details.service_name,
        "account_id": details.account_id,
        "invoice_entity": details.invoice_entity,
        "invoice_id": details.invoice_id,
        "amount": details.amount,
        "error": details.error,
    }
    assert actual == expected
