from decimal import Decimal

import pytest

from swo_aws_extension.flows.jobs.billing_journal.generators.line_processors.marketplace import (
    MarketplaceJournalLineProcessor,
)
from swo_aws_extension.flows.jobs.billing_journal.models.context import LineProcessorContext
from swo_aws_extension.flows.jobs.billing_journal.models.invoice import OrganizationInvoice
from swo_aws_extension.flows.jobs.billing_journal.models.journal_line import JournalDetails
from swo_aws_extension.flows.jobs.billing_journal.models.usage import AccountUsage, ServiceMetric


@pytest.fixture
def processor():
    return MarketplaceJournalLineProcessor()


@pytest.fixture
def context():
    return LineProcessorContext(
        account_id="ACC-001",
        account_usage=AccountUsage(),
        journal_details=JournalDetails(
            agreement_id="AGR-123",
            mpa_id="MPA-456",
            start_date="2026-01-01",
            end_date="2026-01-31",
        ),
        organization_invoice=OrganizationInvoice(),
    )


def test_process_skips_tax_service(processor, context):
    metric = ServiceMetric(
        service_name="Tax",
        record_type="MARKETPLACE",
        amount=Decimal("248.98"),
    )

    result = processor.process(metric, context)

    assert result == []


def test_process_returns_line_for_non_tax_service(processor, context):
    metric = ServiceMetric(
        service_name="CloudGuard Network Security",
        record_type="MARKETPLACE",
        amount=Decimal("1310.40"),
    )

    result = processor.process(metric, context)

    assert len(result) == 1
    assert result[0].price.pp_x1 == Decimal("1310.40")
    assert result[0].description.value1 == "CloudGuard Network Security"
