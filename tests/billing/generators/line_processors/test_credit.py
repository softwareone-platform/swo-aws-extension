from decimal import Decimal

import pytest

from swo_aws_extension.billing.generators.line_processors.credit import (
    CREDIT_PREFIX,
    SPP_PREFIX,
    SPP_SUFFIX,
    CreditJournalLineProcessor,
    SppRecoveryJournalLineProcessor,
)
from swo_aws_extension.billing.models.context import LineProcessorContext
from swo_aws_extension.billing.models.invoice import OrganizationInvoice
from swo_aws_extension.billing.models.journal_line import JournalDetails
from swo_aws_extension.billing.models.usage import AccountUsage, ServiceMetric
from swo_aws_extension.constants import AWSRecordTypeEnum, ItemSkuEnum


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
    return CreditJournalLineProcessor()


@pytest.fixture
def credit_metric():
    return ServiceMetric(
        service_name="Amazon S3",
        record_type=AWSRecordTypeEnum.CREDIT,
        amount=Decimal("-50.00"),
        invoice_entity="AWS Inc.",
        start_date="2026-01-01",
        end_date="2026-01-31",
    )


@pytest.fixture
def spp_metric():
    return ServiceMetric(
        service_name="Amazon S3",
        record_type=AWSRecordTypeEnum.SOLUTION_PROVIDER_PROGRAM_DISCOUNT,
        amount=Decimal("-5.00"),
        invoice_entity="AWS Inc.",
        start_date="2026-01-01",
        end_date="2026-01-31",
    )


def test_process_skips_zero_amount(processor, journal_details):
    metric = ServiceMetric(
        service_name="Amazon S3",
        record_type=AWSRecordTypeEnum.CREDIT,
        amount=Decimal(0),
        start_date="2026-01-01",
        end_date="2026-01-31",
    )
    context = LineProcessorContext(
        account_id="ACC-001",
        account_usage=AccountUsage(),
        journal_details=journal_details,
        organization_invoice=OrganizationInvoice(),
    )

    result = processor.process(metric, context)

    assert result == []


@pytest.mark.parametrize(
    ("include_spp_metric", "principal_invoice_amount"),
    [
        (False, Decimal("100.00")),
        (True, Decimal("100.00")),
        (False, Decimal(0)),
    ],
)
def test_process_does_not_add_spp_for_non_applicable_scenarios(
    processor,
    credit_metric,
    spp_metric,
    journal_details,
    include_spp_metric,
    principal_invoice_amount,
):
    metrics = [credit_metric, spp_metric] if include_spp_metric else [credit_metric]
    context = LineProcessorContext(
        account_id="ACC-001",
        account_usage=AccountUsage(metrics=metrics),
        journal_details=journal_details,
        organization_invoice=OrganizationInvoice(
            principal_invoice_amount=principal_invoice_amount,
        ),
    )

    result = processor.process(credit_metric, context)

    assert len(result) == 1
    assert result[0].description.value1 == f"{CREDIT_PREFIX}Amazon S3"


def test_process_adds_spp_when_principal_zero(
    processor,
    credit_metric,
    spp_metric,
    journal_details,
):
    context = LineProcessorContext(
        account_id="ACC-001",
        account_usage=AccountUsage(metrics=[credit_metric, spp_metric]),
        journal_details=journal_details,
        organization_invoice=OrganizationInvoice(
            principal_invoice_amount=Decimal(0),
        ),
    )

    result = processor.process(credit_metric, context)

    assert len(result) == 2
    assert result[0].description.value1 == f"{CREDIT_PREFIX}Amazon S3"
    assert result[1].description.value1 == f"{SPP_PREFIX}Amazon S3{SPP_SUFFIX}"
    assert result[1].price.pp_x1 == Decimal("-5.00")


def test_process_matches_spp_by_period_not_first_in_list(
    processor,
    journal_details,
):
    credit_jan02 = ServiceMetric(
        service_name="Amazon CloudWatch",
        record_type=AWSRecordTypeEnum.CREDIT,
        amount=Decimal("-2.00"),
        invoice_entity="AWS Inc.",
        start_date="2026-01-02",
        end_date="2026-01-02",
    )
    spp_jan01 = ServiceMetric(
        service_name="Amazon CloudWatch",
        record_type=AWSRecordTypeEnum.SOLUTION_PROVIDER_PROGRAM_DISCOUNT,
        amount=Decimal("-0.11"),
        invoice_entity="AWS Inc.",
        start_date="2026-01-01",
        end_date="2026-01-01",
    )
    spp_jan02 = ServiceMetric(
        service_name="Amazon CloudWatch",
        record_type=AWSRecordTypeEnum.SOLUTION_PROVIDER_PROGRAM_DISCOUNT,
        amount=Decimal("-0.22"),
        invoice_entity="AWS Inc.",
        start_date="2026-01-02",
        end_date="2026-01-02",
    )
    context = LineProcessorContext(
        account_id="ACC-001",
        account_usage=AccountUsage(metrics=[credit_jan02, spp_jan01, spp_jan02]),
        journal_details=journal_details,
        organization_invoice=OrganizationInvoice(principal_invoice_amount=Decimal(0)),
    )

    result = processor.process(credit_jan02, context)

    assert len(result) == 2
    assert result[1].price.pp_x1 == Decimal("-0.22"), (
        "SPP line must use the Jan-02 SPP metric, not the first (Jan-01) one"
    )


def test_process_skips_spp_when_no_matching_period(
    processor,
    journal_details,
):
    credit_jan02 = ServiceMetric(
        service_name="AWS Data Transfer",
        record_type=AWSRecordTypeEnum.CREDIT,
        amount=Decimal("-1.00"),
        invoice_entity="AWS Inc.",
        start_date="2026-01-02",
        end_date="2026-01-02",
    )
    spp_jan01 = ServiceMetric(
        service_name="AWS Data Transfer",
        record_type=AWSRecordTypeEnum.SOLUTION_PROVIDER_PROGRAM_DISCOUNT,
        amount=Decimal("-0.10"),
        invoice_entity="AWS Inc.",
        start_date="2026-01-01",
        end_date="2026-01-01",
    )
    context = LineProcessorContext(
        account_id="ACC-001",
        account_usage=AccountUsage(metrics=[credit_jan02, spp_jan01]),
        journal_details=journal_details,
        organization_invoice=OrganizationInvoice(principal_invoice_amount=Decimal(0)),
    )

    result = processor.process(credit_jan02, context)

    assert len(result) == 1
    assert result[0].description.value1 == f"{CREDIT_PREFIX}AWS Data Transfer"


def test_spp_recovery_processor_uses_usage_sku_for_spp_metric(journal_details, spp_metric):
    context = LineProcessorContext(
        account_id="ACC-001",
        account_usage=AccountUsage(metrics=[spp_metric]),
        journal_details=journal_details,
        organization_invoice=OrganizationInvoice(),
    )

    result = SppRecoveryJournalLineProcessor().process(spp_metric, context)

    assert len(result) == 1
    assert result[0].search.search_item.criteria_value == ItemSkuEnum.ADDITIONAL_CHARGES_SKU
    assert result[0].description.value1 == f"{SPP_PREFIX}Amazon S3{SPP_SUFFIX}"
