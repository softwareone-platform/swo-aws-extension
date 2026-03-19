from decimal import Decimal

import pytest

from swo_aws_extension.constants import AWSRecordTypeEnum
from swo_aws_extension.flows.jobs.billing_journal.generators.line_processors.credit import (
    CREDIT_PREFIX,
    SPP_PREFIX,
    SPP_SUFFIX,
    CreditLineProcessor,
)
from swo_aws_extension.flows.jobs.billing_journal.models.context import LineProcessorContext
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
def processor():
    return CreditLineProcessor()


@pytest.fixture
def credit_metric():
    return ServiceMetric(
        service_name="Amazon S3",
        record_type=AWSRecordTypeEnum.CREDIT,
        amount=Decimal("-50.00"),
        invoice_entity="AWS Inc.",
    )


@pytest.fixture
def spp_metric():
    return ServiceMetric(
        service_name="Amazon S3",
        record_type=AWSRecordTypeEnum.SOLUTION_PROVIDER_PROGRAM_DISCOUNT,
        amount=Decimal("-5.00"),
        invoice_entity="AWS Inc.",
    )


def test_process_skips_zero_amount(processor, journal_details):
    metric = ServiceMetric(
        service_name="Amazon S3",
        record_type=AWSRecordTypeEnum.CREDIT,
        amount=Decimal(0),
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


@pytest.mark.parametrize("principal_invoice_amount", [None, Decimal(0)])
def test_process_adds_spp_when_principal_zero(
    processor, credit_metric, spp_metric, journal_details, principal_invoice_amount
):
    context = LineProcessorContext(
        account_id="ACC-001",
        account_usage=AccountUsage(metrics=[credit_metric, spp_metric]),
        journal_details=journal_details,
        organization_invoice=OrganizationInvoice(
            principal_invoice_amount=principal_invoice_amount,
        ),
    )

    result = processor.process(credit_metric, context)

    assert len(result) == 2
    assert result[0].description.value1 == f"{CREDIT_PREFIX}Amazon S3"
    assert result[1].description.value1 == f"{SPP_PREFIX}Amazon S3{SPP_SUFFIX}"
    assert result[1].price.pp_x1 == Decimal("-5.00")
