from decimal import Decimal

from swo_aws_extension.constants import AWSRecordTypeEnum
from swo_aws_extension.flows.jobs.billing_journal.generators.billing_report_rows import (
    ReportContext,
    generate_billing_report_rows,
)
from swo_aws_extension.flows.jobs.billing_journal.models.context import (
    AuthorizationContext,
)
from swo_aws_extension.flows.jobs.billing_journal.models.invoice import (
    InvoiceEntity,
    OrganizationInvoice,
)
from swo_aws_extension.flows.jobs.billing_journal.models.journal_line import JournalDetails
from swo_aws_extension.flows.jobs.billing_journal.models.journal_result import BillingReportRow
from swo_aws_extension.flows.jobs.billing_journal.models.usage import (
    AccountUsage,
    OrganizationReport,
    OrganizationUsageResult,
    ServiceMetric,
)

SMALL_AMOUNT = 50
MEDIUM_AMOUNT = 100
AGGREGATED_AMOUNT = 150
TEST_AMOUNT_M5 = -5


def test_generate_billing_report_rows_aggregates_metrics():
    metric1 = ServiceMetric(
        "EC2", AWSRecordTypeEnum.USAGE, Decimal(MEDIUM_AMOUNT), "INV-E1", "INV-1"
    )
    metric2 = ServiceMetric(
        "EC2", AWSRecordTypeEnum.USAGE, Decimal(SMALL_AMOUNT), "INV-E1", "INV-1"
    )
    metric3 = ServiceMetric(
        "EC2",
        AWSRecordTypeEnum.SOLUTION_PROVIDER_PROGRAM_DISCOUNT,
        Decimal(TEST_AMOUNT_M5),
        "INV-E1",
        "INV-1",
    )
    account_usage = AccountUsage([metric1, metric2, metric3])
    usage_result = OrganizationUsageResult(
        reports=OrganizationReport(), usage_by_account={"ACC-1": account_usage}
    )
    org_invoice = OrganizationInvoice(
        entities={"INV-E1": InvoiceEntity("INV-1", "USD", "USD", Decimal("1.2"))}
    )
    context = ReportContext("AUTH-1", "PMA-1", "AGR-1", "MPA-1", "USD")
    expected_row = BillingReportRow(
        authorization_id="AUTH-1",
        pma="PMA-1",
        agreement_id="AGR-1",
        mpa="MPA-1",
        service_name="EC2",
        amount=Decimal(AGGREGATED_AMOUNT),
        currency="USD",
        invoice_id="INV-1",
        invoice_entity="INV-E1",
        exchange_rate=Decimal("1.2"),
        spp_discount=Decimal(TEST_AMOUNT_M5),
    )

    result = generate_billing_report_rows(context, usage_result, org_invoice)

    assert len(result) == 1
    assert result[0] == expected_row


def test_report_context_from_contexts_builds_correctly():
    auth_context = AuthorizationContext(id="AUTH-1", pma_account="PMA-1", currency="USD")
    journal_details = JournalDetails(
        agreement_id="AGR-1",
        mpa_id="MPA-1",
        start_date="2024-01-01",
        end_date="2024-01-31",
    )

    context = ReportContext.from_contexts(auth_context, journal_details)  # act

    assert context.authorization_id == "AUTH-1"
    assert context.pma == "PMA-1"
    assert context.agreement_id == "AGR-1"
    assert context.mpa == "MPA-1"
    assert context.currency == "USD"


def test_generate_billing_report_rows_defaults_exchange_rate_and_warns_for_unknown_entity(
    caplog,
):
    metric = ServiceMetric(
        "EC2", AWSRecordTypeEnum.USAGE, Decimal(MEDIUM_AMOUNT), "UNKNOWN-ENTITY", "INV-X"
    )
    account_usage = AccountUsage([metric])
    usage_result = OrganizationUsageResult(
        reports=OrganizationReport(), usage_by_account={"ACC-1": account_usage}
    )
    org_invoice = OrganizationInvoice(entities={})
    context = ReportContext("AUTH-1", "PMA-1", "AGR-1", "MPA-1", "USD")

    result = generate_billing_report_rows(context, usage_result, org_invoice)  # act

    assert len(result) == 1
    assert result[0].exchange_rate == Decimal("1.0")
    assert "No exchange rate found for invoice entity 'UNKNOWN-ENTITY'" in caplog.text
