from decimal import Decimal

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.billing.generators.billing_report_rows import (
    BillingReportRowsBuilder,
    ReportContext,
)
from swo_aws_extension.billing.models.context import (
    AuthorizationContext,
)
from swo_aws_extension.billing.models.invoice import (
    InvoiceEntity,
    OrganizationInvoice,
)
from swo_aws_extension.billing.models.journal_line import JournalDetails
from swo_aws_extension.billing.models.journal_result import BillingReportRow
from swo_aws_extension.billing.models.usage import (
    AccountUsage,
    OrganizationReport,
    OrganizationUsageResult,
    ServiceMetric,
)
from swo_aws_extension.constants import AWSRecordTypeEnum

SMALL_AMOUNT = 50
MEDIUM_AMOUNT = 100
AGGREGATED_AMOUNT = 150
TEST_AMOUNT_M5 = -5


def test_generate_billing_report_rows_aggregates_metrics():
    metric1 = ServiceMetric(
        service_name="EC2",
        record_type=AWSRecordTypeEnum.USAGE,
        start_date="2026-01-01",
        end_date="2026-01-31",
        amount=Decimal(MEDIUM_AMOUNT),
        invoice_entity="INV-E1",
        invoice_id="INV-1",
    )
    metric2 = ServiceMetric(
        service_name="EC2",
        record_type=AWSRecordTypeEnum.USAGE,
        start_date="2026-01-01",
        end_date="2026-01-31",
        amount=Decimal(SMALL_AMOUNT),
        invoice_entity="INV-E1",
        invoice_id="INV-1",
    )
    metric3 = ServiceMetric(
        service_name="EC2",
        record_type=AWSRecordTypeEnum.SOLUTION_PROVIDER_PROGRAM_DISCOUNT,
        start_date="2026-01-01",
        end_date="2026-01-31",
        amount=Decimal(TEST_AMOUNT_M5),
        invoice_entity="INV-E1",
        invoice_id="INV-1",
    )
    account_usage = AccountUsage([metric1, metric2, metric3])
    usage_result = OrganizationUsageResult(
        reports=OrganizationReport(), usage_by_account={"ACC-1": account_usage}
    )
    exchange_rate = Decimal("1.2")
    org_invoice = OrganizationInvoice(
        entities={"INV-E1": InvoiceEntity("INV-1", "USD", "USD", exchange_rate)},
    )
    context = ReportContext("AUTH-1", "PMA-1", "AGR-1", "MPA-1", "USD")
    expected_row = BillingReportRow(
        authorization_id="AUTH-1",
        pma="PMA-1",
        agreement_id="AGR-1",
        mpa="MPA-1",
        service_name="EC2",
        pp=(Decimal(AGGREGATED_AMOUNT) - abs(Decimal(TEST_AMOUNT_M5))) * exchange_rate,
        sp=Decimal(AGGREGATED_AMOUNT) * exchange_rate,
        currency="USD",
        invoice_id="INV-1",
        invoice_entity="INV-E1",
        exchange_rate=exchange_rate,
        spp_discount=Decimal(TEST_AMOUNT_M5) * exchange_rate,
        spp_discount_pct=abs(Decimal(TEST_AMOUNT_M5)) / (Decimal(AGGREGATED_AMOUNT)),
    )

    result = BillingReportRowsBuilder(context, usage_result, org_invoice).build()

    assert len(result) == 1
    assert result[0] == expected_row


def test_report_context_from_contexts_builds_correctly(mocker):
    auth_context = AuthorizationContext(
        id="AUTH-1",
        pma_account="PMA-1",
        currency="USD",
        aws_client=mocker.MagicMock(spec=AWSClient),
    )
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


def test_generate_billing_report_rows_defaults_exchange_rate_for_unknown_entity():
    metric = ServiceMetric(
        service_name="EC2",
        record_type=AWSRecordTypeEnum.USAGE,
        start_date="2026-01-01",
        end_date="2026-01-31",
        amount=Decimal(MEDIUM_AMOUNT),
        invoice_entity="UNKNOWN-ENTITY",
        invoice_id="INV-X",
    )
    account_usage = AccountUsage([metric])
    usage_result = OrganizationUsageResult(
        reports=OrganizationReport(), usage_by_account={"ACC-1": account_usage}
    )
    org_invoice = OrganizationInvoice(entities={})
    context = ReportContext("AUTH-1", "PMA-1", "AGR-1", "MPA-1", "USD")

    result = BillingReportRowsBuilder(context, usage_result, org_invoice).build()

    assert len(result) == 1
    assert result[0].exchange_rate == Decimal("1.0")


def test_build_by_account_groups_by_linked_account():
    metric1 = ServiceMetric(
        service_name="EC2",
        record_type=AWSRecordTypeEnum.USAGE,
        start_date="2026-01-01",
        end_date="2026-01-31",
        amount=Decimal(MEDIUM_AMOUNT),
        invoice_entity="INV-E1",
        invoice_id="INV-1",
    )
    metric2 = ServiceMetric(
        service_name="S3",
        record_type=AWSRecordTypeEnum.USAGE,
        start_date="2026-01-01",
        end_date="2026-01-31",
        amount=Decimal(SMALL_AMOUNT),
        invoice_entity="INV-E1",
        invoice_id="INV-1",
    )
    usage_result = OrganizationUsageResult(
        reports=OrganizationReport(),
        usage_by_account={
            "ACC-1": AccountUsage([metric1]),
            "ACC-2": AccountUsage([metric2]),
        },
    )
    org_invoice = OrganizationInvoice(
        entities={"INV-E1": InvoiceEntity("INV-1", "USD", "USD", Decimal("1.0"))},
    )
    context = ReportContext("AUTH-1", "PMA-1", "AGR-1", "MPA-1", "USD")

    result = BillingReportRowsBuilder(context, usage_result, org_invoice).build_by_account()

    assert len(result) == 2
    accounts = {row.linked_account for row in result}
    assert accounts == {"ACC-1", "ACC-2"}
