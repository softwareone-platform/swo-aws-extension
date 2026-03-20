from decimal import Decimal

import pytest

from swo_aws_extension.constants import AWSRecordTypeEnum
from swo_aws_extension.flows.jobs.billing_journal.generators.line_processors.base import (
    LineProcessor,
)
from swo_aws_extension.flows.jobs.billing_journal.models.context import LineProcessorContext
from swo_aws_extension.flows.jobs.billing_journal.models.invoice import (
    InvoiceEntity,
    OrganizationInvoice,
)
from swo_aws_extension.flows.jobs.billing_journal.models.journal_line import JournalDetails
from swo_aws_extension.flows.jobs.billing_journal.models.usage import AccountUsage, ServiceMetric


def build_context_with_invoice(
    journal_details,
    payment_currency_code="",
    base_currency_code="",
    exchange_rate=0,
):
    organization_invoice = OrganizationInvoice(
        entities={
            "AWS Inc.": InvoiceEntity(
                base_currency_code=base_currency_code,
                payment_currency_code=payment_currency_code,
                exchange_rate=Decimal(exchange_rate),
            )
        },
    )
    return LineProcessorContext(
        account_id="ACC-001",
        account_usage=AccountUsage(),
        journal_details=journal_details,
        organization_invoice=organization_invoice,
    )


@pytest.fixture
def journal_details():
    return JournalDetails(
        agreement_id="AGR-123",
        mpa_id="MPA-456",
        start_date="2026-01-01",
        end_date="2026-01-31",
    )


@pytest.fixture
def processor():
    return LineProcessor()


@pytest.fixture
def context(journal_details):
    return LineProcessorContext(
        account_id="ACC-001",
        account_usage=AccountUsage(),
        journal_details=journal_details,
        organization_invoice=OrganizationInvoice(),
    )


@pytest.fixture
def usage_metric():
    return ServiceMetric(
        service_name="Amazon S3",
        record_type=AWSRecordTypeEnum.USAGE,
        amount=Decimal("100.00"),
        invoice_entity="AWS Inc.",
    )


def test_process_returns_journal_line(processor, context):
    metric = ServiceMetric(
        service_name="Amazon S3",
        record_type=AWSRecordTypeEnum.USAGE,
        amount=Decimal("100.50"),
        invoice_entity="AWS Inc.",
        invoice_id="INV-001",
    )

    result = processor.process(metric, context)

    assert len(result) == 1
    assert result[0].price.pp_x1 == Decimal("100.50")
    assert result[0].description.value1 == "Amazon S3"


def test_process_skips_zero_amount(processor, context):
    metric = ServiceMetric(
        service_name="Amazon S3",
        record_type=AWSRecordTypeEnum.USAGE,
        amount=Decimal(0),
    )

    result = processor.process(metric, context)

    assert result == []


def test_process_uses_default_invoice_id(processor, context):
    metric = ServiceMetric(
        service_name="Amazon S3",
        record_type=AWSRecordTypeEnum.USAGE,
        amount=Decimal("10.00"),
    )

    result = processor.process(metric, context)

    assert result[0].external_ids.invoice == "invoice_id"


@pytest.mark.parametrize(
    ("prefix_name", "suffix_name", "expected_name"),
    [
        ("PREFIX - ", "", "PREFIX - Amazon S3"),
        ("PRE - ", " - SUF", "PRE - Amazon S3 - SUF"),
    ],
)
def test_process_applies_name_affixes(context, prefix_name, suffix_name, expected_name):
    processor = LineProcessor(prefix_name=prefix_name, suffix_name=suffix_name)
    metric = ServiceMetric(
        service_name="Amazon S3",
        record_type=AWSRecordTypeEnum.USAGE,
        amount=Decimal("10.00"),
    )

    result = processor.process(metric, context)

    assert result[0].description.value1 == expected_name


@pytest.mark.parametrize(
    (
        "payment_currency_code",
        "base_currency_code",
        "exchange_rate",
        "expected_amount",
    ),
    [
        ("EUR", "USD", "0.95", Decimal("95.000000")),
        ("EUR", "EUR", "0.95", Decimal("100.00")),
        ("EUR", "USD", "0", Decimal("100.00")),
    ],
)
def test_process_resolves_amount_with_exchange_rate_rules(
    processor,
    usage_metric,
    journal_details,
    payment_currency_code,
    base_currency_code,
    exchange_rate,
    expected_amount,
):
    context = build_context_with_invoice(
        journal_details=journal_details,
        payment_currency_code=payment_currency_code,
        base_currency_code=base_currency_code,
        exchange_rate=exchange_rate,
    )

    result = processor.process(usage_metric, context)

    assert result[0].price.pp_x1 == expected_amount
