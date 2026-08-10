from decimal import Decimal

import pytest

from swo_aws_extension.constants import AWSRecordTypeEnum
from swo_aws_extension.flows.jobs.billing_journal.generators.line_processors.credit import (
    CREDIT_PREFIX,
    CreditJournalLineProcessor,
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
def credit_metric():
    return ServiceMetric(
        service_name="Amazon S3",
        record_type=AWSRecordTypeEnum.CREDIT,
        amount=Decimal("-50.00"),
        invoice_entity="AWS Inc.",
    )


def test_process_generates_line_with_prefix(journal_details, credit_metric):
    context = LineProcessorContext(
        account_id="ACC-001",
        account_usage=AccountUsage(metrics=[credit_metric]),
        journal_details=journal_details,
        organization_invoice=OrganizationInvoice(),
    )

    result = CreditJournalLineProcessor().process(credit_metric, context)

    assert len(result) == 1
    assert result[0].description.value1 == f"{CREDIT_PREFIX}Amazon S3"
    assert result[0].price.pp_x1 == Decimal("-50.00")
