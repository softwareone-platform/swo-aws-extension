from decimal import Decimal

import pytest

from swo_aws_extension.flows.jobs.billing_journal.generators.line_processors.support import (
    SupportJournalLineProcessor,
)
from swo_aws_extension.flows.jobs.billing_journal.models.context import LineProcessorContext
from swo_aws_extension.flows.jobs.billing_journal.models.invoice import (
    InvoiceEntity,
    OrganizationInvoice,
)
from swo_aws_extension.flows.jobs.billing_journal.models.journal_line import JournalDetails
from swo_aws_extension.flows.jobs.billing_journal.models.usage import (
    AccountUsage,
    ServiceMetric,
)


@pytest.fixture
def processor_context():
    return LineProcessorContext(
        account_id="ACC-001",
        account_usage=AccountUsage(),
        journal_details=JournalDetails("AGR-1", "MPA-1", "2023-01-01", "2023-01-31"),
        organization_invoice=OrganizationInvoice(
            entities={
                "INV-1": InvoiceEntity(
                    invoice_id="INV-001",
                    base_currency_code="USD",
                    payment_currency_code="USD",
                    exchange_rate=Decimal("1.0"),
                )
            }
        ),
        is_pls=False,
    )


def test_excludes_enterprise_support_when_pls_active(processor_context):
    processor_context.is_pls = True
    metric = ServiceMetric(
        service_name="AWS Support (Enterprise)",
        record_type="Support",
        amount=Decimal("100.00"),
        invoice_entity="INV-1",
        invoice_id="INV-001",
    )
    processor = SupportJournalLineProcessor()

    result = processor.process(metric, processor_context)

    assert not result


@pytest.mark.parametrize(
    ("is_pls", "service_name"),
    [
        (True, "AWS Support (Developer)"),
        (False, "AWS Support (Enterprise)"),
        (False, "AWS Support (Business)"),
    ],
)
def test_includes_non_excluded_support(processor_context, is_pls, service_name):
    processor_context.is_pls = is_pls
    metric = ServiceMetric(
        service_name=service_name,
        record_type="Support",
        amount=Decimal("100.00"),
        invoice_entity="INV-1",
        invoice_id="INV-001",
    )
    processor = SupportJournalLineProcessor()

    result = processor.process(metric, processor_context)

    assert len(result) == 1
    assert result[0].price.unit_pp == Decimal("100.00")
    assert result[0].description.value1 == service_name
