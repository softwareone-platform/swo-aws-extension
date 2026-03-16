from decimal import Decimal

import pytest

from swo_aws_extension.constants import AWSRecordTypeEnum
from swo_aws_extension.flows.jobs.billing_journal.generators.journal_line import (
    JournalLineGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.models.journal_line import JournalDetails
from swo_aws_extension.flows.jobs.billing_journal.models.usage import AccountUsage, ServiceMetric


@pytest.fixture
def journal_details():
    return JournalDetails(
        agreement_id="AGR-123",
        mpa_id="MPA-456",
        start_date="2026-01-01",
        end_date="2026-01-31",
    )


@pytest.fixture
def generator():
    return JournalLineGenerator()


def test_generate_single_metric(journal_details, generator):
    metric = ServiceMetric(
        service_name="Amazon S3",
        record_type=AWSRecordTypeEnum.USAGE,
        amount=Decimal("100.50"),
        invoice_entity="AWS Inc.",
    )
    account_usage = AccountUsage(metrics=[metric])

    result = generator.generate("ACC-001", account_usage, journal_details)

    assert len(result) == 1
    assert result[0].price.pp_x1 == Decimal("100.50")


def test_generate_multiple_metrics(journal_details, generator):
    metrics = [
        ServiceMetric(
            service_name="Amazon S3",
            record_type=AWSRecordTypeEnum.USAGE,
            amount=Decimal("100.00"),
            invoice_entity="AWS Inc.",
        ),
        ServiceMetric(
            service_name="Amazon S3",
            record_type=AWSRecordTypeEnum.SUPPORT,
            amount=Decimal("10.00"),
            invoice_entity="AWS Inc.",
        ),
        ServiceMetric(
            service_name="Amazon EC2",
            record_type=AWSRecordTypeEnum.RECURRING,
            amount=Decimal("50.00"),
            invoice_entity="AWS Inc.",
        ),
    ]
    account_usage = AccountUsage(metrics=metrics)

    result = generator.generate("ACC-001", account_usage, journal_details)

    assert len(result) == 3


@pytest.mark.parametrize(
    ("metrics", "expected_count"),
    [
        ([], 0),
        (
            [
                ServiceMetric(
                    service_name="Amazon S3",
                    record_type=AWSRecordTypeEnum.USAGE,
                    amount=Decimal(0),
                )
            ],
            0,
        ),
    ],
)
def test_generate_returns_empty_for_no_metrics(journal_details, generator, metrics, expected_count):
    account_usage = AccountUsage(metrics=metrics)

    result = generator.generate("ACC-001", account_usage, journal_details)

    assert len(result) == expected_count


def test_generate_excludes_non_billable_record_types(journal_details, generator):
    metrics = [
        ServiceMetric(
            service_name="Amazon S3",
            record_type=AWSRecordTypeEnum.USAGE,
            amount=Decimal("100.00"),
        ),
        ServiceMetric(
            service_name="Amazon S3",
            record_type=AWSRecordTypeEnum.SOLUTION_PROVIDER_PROGRAM_DISCOUNT,
            amount=Decimal("-10.00"),
        ),
        ServiceMetric(
            service_name="Tax",
            record_type="Tax",
            amount=Decimal("10.00"),
        ),
    ]
    account_usage = AccountUsage(metrics=metrics)

    result = generator.generate("ACC-001", account_usage, journal_details)

    assert len(result) == 1
    assert result[0].description.value1 == "Amazon S3"


def test_generate_includes_all_billable_record_types(journal_details, generator):
    billable_types = [
        AWSRecordTypeEnum.USAGE,
        AWSRecordTypeEnum.SUPPORT,
        AWSRecordTypeEnum.RECURRING,
        AWSRecordTypeEnum.SAVING_PLAN_RECURRING_FEE,
        "MARKETPLACE",
    ]
    metrics = [
        ServiceMetric(
            service_name="Amazon S3",
            record_type=record_type,
            amount=Decimal("10.00"),
        )
        for record_type in billable_types
    ]
    account_usage = AccountUsage(metrics=metrics)

    result = generator.generate("ACC-001", account_usage, journal_details)

    assert len(result) == len(billable_types)


@pytest.mark.parametrize(
    ("invoice_id", "expected_invoice_id"),
    [
        ("INV-2026-001", "INV-2026-001"),
        (None, "invoice_id"),
    ],
)
def test_generate_handles_invoice_id(journal_details, generator, invoice_id, expected_invoice_id):
    metric = ServiceMetric(
        service_name="Amazon S3",
        record_type=AWSRecordTypeEnum.USAGE,
        amount=Decimal("100.00"),
        invoice_id=invoice_id,
    )
    account_usage = AccountUsage(metrics=[metric])

    result = generator.generate("ACC-001", account_usage, journal_details)

    assert result[0].external_ids.invoice == expected_invoice_id


def test_generate_includes_invoice_entity(journal_details, generator):
    metric = ServiceMetric(
        service_name="Amazon S3",
        record_type=AWSRecordTypeEnum.USAGE,
        amount=Decimal("100.00"),
        invoice_entity="AWS Inc.",
    )
    account_usage = AccountUsage(metrics=[metric])

    result = generator.generate("ACC-001", account_usage, journal_details)

    assert "AWS Inc." in result[0].description.value2
