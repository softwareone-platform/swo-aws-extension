from decimal import Decimal

import pytest

from swo_aws_extension.billing.generators.line_processors.saving_plans import (
    SavingsPlanJournalLineProcessor,
)
from swo_aws_extension.billing.models.context import LineProcessorContext
from swo_aws_extension.billing.models.invoice import InvoiceEntity, OrganizationInvoice
from swo_aws_extension.billing.models.journal_line import JournalDetails
from swo_aws_extension.billing.models.usage import AccountUsage, ServiceMetric
from swo_aws_extension.constants import AWSRecordTypeEnum


@pytest.fixture
def metric():
    return ServiceMetric(
        service_name="AWS Savings Plans",
        record_type=AWSRecordTypeEnum.SAVING_PLAN_RECURRING_FEE,
        amount=Decimal("1000.00"),
        invoice_entity="INV-1",
        invoice_id="INV-001",
        start_date="2025-01-01",
        end_date="2025-01-31",
    )


@pytest.fixture
def processor_context():
    return LineProcessorContext(
        account_id="MPA-001",
        account_usage=AccountUsage(),
        journal_details=JournalDetails(
            agreement_id="AGR-1",
            mpa_id="MPA-001",
            start_date="2025-01-01",
            end_date="2025-01-31",
            split_billing_enabled=False,
        ),
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
    )


def test_skips_recurring_fee_when_split_billing_enabled(processor_context, metric):
    processor_context.journal_details.split_billing_enabled = True

    result = SavingsPlanJournalLineProcessor().process(metric, processor_context)

    assert result == []


def test_processes_recurring_fee_when_split_billing_disabled(processor_context, metric):
    processor_context.journal_details.split_billing_enabled = False

    result = SavingsPlanJournalLineProcessor().process(metric, processor_context)

    assert len(result) == 1
    assert result[0].price.pp_x1 == Decimal("1000.00")


def test_routes_to_master_payer_subscription_when_not_split(processor_context, metric):
    processor_context.journal_details.split_billing_enabled = False

    result = SavingsPlanJournalLineProcessor().process(metric, processor_context)

    source = result[0].search.source
    assert source.type == "Subscription"
    assert source.criteria_value == "MPA-001"
