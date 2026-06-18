from decimal import Decimal

import pytest

from swo_aws_extension.billing.generators.journal_line import (
    JournalLineGenerator,
)
from swo_aws_extension.billing.generators.line_processors.bundle_discount import (
    BUNDLE_DISCOUNT_PREFIX,
)
from swo_aws_extension.billing.models.invoice import OrganizationInvoice
from swo_aws_extension.billing.models.journal_line import JournalDetails
from swo_aws_extension.billing.models.usage import AccountUsage, ServiceMetric
from swo_aws_extension.constants import AWSRecordTypeEnum


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


def test_bundle_discount_metric_has_prefix(journal_details, generator, organization_invoice):
    metric = ServiceMetric(
        service_name="Amazon S3",
        record_type=AWSRecordTypeEnum.BUNDLE_DISCOUNT,
        amount=Decimal("-25.00"),
    )
    account_usage = AccountUsage(metrics=[metric])

    result = generator.generate("ACC-001", account_usage, journal_details, organization_invoice)

    assert len(result) == 1
    assert result[0].description.value1 == f"{BUNDLE_DISCOUNT_PREFIX}Amazon S3"


def test_bundle_discount_skips_zero_amount(journal_details, generator, organization_invoice):
    metric = ServiceMetric(
        service_name="Amazon S3",
        record_type=AWSRecordTypeEnum.BUNDLE_DISCOUNT,
        amount=Decimal(0),
    )
    account_usage = AccountUsage(metrics=[metric])

    result = generator.generate("ACC-001", account_usage, journal_details, organization_invoice)

    assert len(result) == 0


def test_bundle_discount_preserves_amount(journal_details, generator, organization_invoice):
    metric = ServiceMetric(
        service_name="Amazon EC2",
        record_type=AWSRecordTypeEnum.BUNDLE_DISCOUNT,
        amount=Decimal("-15.75"),
    )
    account_usage = AccountUsage(metrics=[metric])

    result = generator.generate("ACC-001", account_usage, journal_details, organization_invoice)

    assert len(result) == 1
    assert result[0].price.pp_x1 == Decimal("-15.75")


def test_bundle_discount_multiple_services(journal_details, generator, organization_invoice):
    metrics = [
        ServiceMetric(
            service_name="Amazon S3",
            record_type=AWSRecordTypeEnum.BUNDLE_DISCOUNT,
            amount=Decimal("-10.00"),
        ),
        ServiceMetric(
            service_name="Amazon EC2",
            record_type=AWSRecordTypeEnum.BUNDLE_DISCOUNT,
            amount=Decimal("-20.00"),
        ),
    ]
    account_usage = AccountUsage(metrics=metrics)

    result = generator.generate("ACC-001", account_usage, journal_details, organization_invoice)

    assert len(result) == 2
    assert result[0].description.value1 == f"{BUNDLE_DISCOUNT_PREFIX}Amazon S3"
    assert result[1].description.value1 == f"{BUNDLE_DISCOUNT_PREFIX}Amazon EC2"


def test_bundle_discount_includes_invoice_entity(journal_details, generator, organization_invoice):
    metric = ServiceMetric(
        service_name="Amazon S3",
        record_type=AWSRecordTypeEnum.BUNDLE_DISCOUNT,
        amount=Decimal("-25.00"),
        invoice_entity="AWS Inc.",
    )
    account_usage = AccountUsage(metrics=[metric])

    result = generator.generate("ACC-001", account_usage, journal_details, organization_invoice)

    assert len(result) == 1
    assert "AWS Inc." in result[0].description.value2
