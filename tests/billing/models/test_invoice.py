from decimal import Decimal

import pytest

from swo_aws_extension.billing.models.invoice import (
    InvoiceEntity,
    OrganizationInvoice,
    OrganizationInvoiceResult,
)

PRIMARY_ENTITY_NAME = "AWS EMEA SARL"
PRIMARY_INVOICE_ID = "INV-001"
SECONDARY_ENTITY_NAME = "AWS Inc."
SECONDARY_INVOICE_ID = "INV-002"


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
