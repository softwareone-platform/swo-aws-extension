from decimal import Decimal

import pytest

from swo_aws_extension.constants import AWSRecordTypeEnum
from swo_aws_extension.flows.jobs.billing_journal.generators.journal_line import (
    JournalLineGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.line_processors.credit import (
    CREDIT_PREFIX,
    SPP_PREFIX,
    SPP_SUFFIX,
)
from swo_aws_extension.flows.jobs.billing_journal.models.invoice import OrganizationInvoice
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


@pytest.fixture
def organization_invoice():
    return OrganizationInvoice()


def test_generate_single_metric(journal_details, generator, organization_invoice):
    metric = ServiceMetric(
        service_name="Amazon S3",
        record_type=AWSRecordTypeEnum.USAGE,
        amount=Decimal("100.50"),
        invoice_entity="AWS Inc.",
    )
    account_usage = AccountUsage(metrics=[metric])

    result = generator.generate("ACC-001", account_usage, journal_details, organization_invoice)

    assert len(result) == 1
    assert result[0].price.pp_x1 == Decimal("100.50")


def test_generate_multiple_metrics(journal_details, generator, organization_invoice):
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

    result = generator.generate("ACC-001", account_usage, journal_details, organization_invoice)

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
def test_generate_returns_empty_for_no_metrics(
    journal_details,
    generator,
    organization_invoice,
    metrics,
    expected_count,
):
    account_usage = AccountUsage(metrics=metrics)

    result = generator.generate("ACC-001", account_usage, journal_details, organization_invoice)

    assert len(result) == expected_count


def test_generate_excludes_non_billable_record_types(
    journal_details,
    generator,
    organization_invoice,
):
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

    result = generator.generate("ACC-001", account_usage, journal_details, organization_invoice)

    assert len(result) == 1
    assert result[0].description.value1 == "Amazon S3"


def test_generate_includes_all_billable_record_types(
    journal_details,
    generator,
    organization_invoice,
):
    billable_types = [
        AWSRecordTypeEnum.USAGE,
        AWSRecordTypeEnum.SUPPORT,
        AWSRecordTypeEnum.RECURRING,
        AWSRecordTypeEnum.SAVING_PLAN_RECURRING_FEE,
        AWSRecordTypeEnum.CREDIT,
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

    result = generator.generate("ACC-001", account_usage, journal_details, organization_invoice)

    assert len(result) == len(billable_types)


@pytest.mark.parametrize(
    ("invoice_id", "expected_invoice_id"),
    [
        ("INV-2026-001", "INV-2026-001"),
        ("", "invoice_id"),
    ],
)
def test_generate_handles_invoice_id(
    journal_details,
    generator,
    organization_invoice,
    invoice_id,
    expected_invoice_id,
):
    metric = ServiceMetric(
        service_name="Amazon S3",
        record_type=AWSRecordTypeEnum.USAGE,
        amount=Decimal("100.00"),
        invoice_id=invoice_id,
    )
    account_usage = AccountUsage(metrics=[metric])

    result = generator.generate("ACC-001", account_usage, journal_details, organization_invoice)

    assert result[0].external_ids.invoice == expected_invoice_id


def test_generate_includes_invoice_entity(journal_details, generator, organization_invoice):
    metric = ServiceMetric(
        service_name="Amazon S3",
        record_type=AWSRecordTypeEnum.USAGE,
        amount=Decimal("100.00"),
        invoice_entity="AWS Inc.",
    )
    account_usage = AccountUsage(metrics=[metric])

    result = generator.generate("ACC-001", account_usage, journal_details, organization_invoice)

    assert "AWS Inc." in result[0].description.value2


def test_generate_credit_metric_has_prefix(journal_details, generator, organization_invoice):
    metric = ServiceMetric(
        service_name="Amazon S3",
        record_type=AWSRecordTypeEnum.CREDIT,
        amount=Decimal("-50.00"),
    )
    account_usage = AccountUsage(metrics=[metric])

    result = generator.generate("ACC-001", account_usage, journal_details, organization_invoice)

    assert len(result) == 1
    assert result[0].description.value1 == f"{CREDIT_PREFIX}Amazon S3"


def test_generate_credit_processor_integration(journal_details, generator):
    metrics = [
        ServiceMetric(
            service_name="Amazon S3",
            record_type=AWSRecordTypeEnum.CREDIT,
            amount=Decimal("-50.00"),
        ),
        ServiceMetric(
            service_name="Amazon S3",
            record_type=AWSRecordTypeEnum.SOLUTION_PROVIDER_PROGRAM_DISCOUNT,
            amount=Decimal("-5.00"),
            invoice_entity="AWS Inc.",
        ),
    ]
    account_usage = AccountUsage(metrics=metrics)
    invoice = OrganizationInvoice(principal_invoice_amount=Decimal(0))

    result = generator.generate("ACC-001", account_usage, journal_details, invoice)

    assert len(result) == 2
    assert result[0].description.value1 == f"{CREDIT_PREFIX}Amazon S3"
    assert result[1].description.value1 == f"{SPP_PREFIX}Amazon S3{SPP_SUFFIX}"
    assert result[1].price.pp_x1 == Decimal("-5.00")
