from decimal import Decimal

import pytest

from swo_aws_extension.billing.generators.additional_line_processors.saving_plans import (
    SavingPlansDistributionProcessor,
)
from swo_aws_extension.billing.models.invoice import OrganizationInvoice
from swo_aws_extension.billing.models.journal_line import JournalDetails
from swo_aws_extension.billing.models.usage import (
    AccountUsage,
    OrganizationReport,
    OrganizationUsageResult,
    ServiceMetric,
)
from swo_aws_extension.constants import AWSRecordTypeEnum, ItemSkuEnum


def _make_metric(record_type, amount, service_name="AWS Savings Plans", invoice_id="INV-001"):
    return ServiceMetric(
        service_name=service_name,
        record_type=record_type,
        amount=Decimal(str(amount)),
        invoice_entity="AWS Inc./AWS",
        invoice_id=invoice_id,
        start_date="2025-01-01",
        end_date="2025-01-31",
    )


def _make_usage_result(
    metrics_by_account: dict[str, list[ServiceMetric]],
) -> OrganizationUsageResult:
    return OrganizationUsageResult(
        reports=OrganizationReport(),
        usage_by_account={
            account_id: AccountUsage(metrics=metrics)
            for account_id, metrics in metrics_by_account.items()
        },
    )


@pytest.fixture
def journal_details():
    return JournalDetails(
        agreement_id="AGR-123",
        mpa_id="MPA-001",
        start_date="2025-01-01",
        end_date="2025-01-31",
        split_billing_enabled=True,
    )


@pytest.fixture
def organization_invoice():
    return OrganizationInvoice()


def test_distributes_sp_fee_proportionally(journal_details, organization_invoice):
    usage_result = _make_usage_result({
        "MPA-001": [_make_metric(AWSRecordTypeEnum.SAVING_PLAN_RECURRING_FEE, "36000")],
        "ACC-A": [_make_metric(AWSRecordTypeEnum.SAVING_PLAN_COVERED_USAGE, "3000")],
        "ACC-B": [_make_metric(AWSRecordTypeEnum.SAVING_PLAN_COVERED_USAGE, "1000")],
    })
    processor = SavingPlansDistributionProcessor()

    result = processor.process(usage_result, journal_details, organization_invoice)

    assert len(result) == 2
    amounts_by_account = {line.search.source.criteria_value: line.price.pp_x1 for line in result}
    assert amounts_by_account["ACC-A"] == Decimal("27000.00")
    assert amounts_by_account["ACC-B"] == Decimal("9000.00")


def test_routes_to_linked_account_subscription(journal_details, organization_invoice):
    usage_result = _make_usage_result({
        "MPA-001": [_make_metric(AWSRecordTypeEnum.SAVING_PLAN_RECURRING_FEE, "1000")],
        "ACC-A": [_make_metric(AWSRecordTypeEnum.SAVING_PLAN_COVERED_USAGE, "500")],
    })
    processor = SavingPlansDistributionProcessor()

    result = processor.process(usage_result, journal_details, organization_invoice)

    assert len(result) == 1
    source = result[0].search.source
    assert source.type == "Subscription"
    assert source.criteria == "externalIds.vendor"
    assert source.criteria_value == "ACC-A"


def test_uses_usage_sku(journal_details, organization_invoice):
    usage_result = _make_usage_result({
        "MPA-001": [_make_metric(AWSRecordTypeEnum.SAVING_PLAN_RECURRING_FEE, "100")],
        "ACC-A": [_make_metric(AWSRecordTypeEnum.SAVING_PLAN_COVERED_USAGE, "100")],
    })
    processor = SavingPlansDistributionProcessor()

    result = processor.process(usage_result, journal_details, organization_invoice)

    assert len(result) == 1
    assert result[0].search.search_item.criteria_value == ItemSkuEnum.USAGE_SKU


def test_skips_account_with_zero_covered_usage(journal_details, organization_invoice):
    usage_result = _make_usage_result({
        "MPA-001": [_make_metric(AWSRecordTypeEnum.SAVING_PLAN_RECURRING_FEE, "1000")],
        "ACC-A": [_make_metric(AWSRecordTypeEnum.SAVING_PLAN_COVERED_USAGE, "800")],
        "ACC-B": [],
    })
    processor = SavingPlansDistributionProcessor()

    result = processor.process(usage_result, journal_details, organization_invoice)

    account_ids = [line.search.source.criteria_value for line in result]
    assert "ACC-A" in account_ids
    assert "ACC-B" not in account_ids


def test_returns_empty_when_no_recurring_fee(journal_details, organization_invoice):
    usage_result = _make_usage_result({
        "ACC-A": [_make_metric(AWSRecordTypeEnum.SAVING_PLAN_COVERED_USAGE, "500")],
    })
    processor = SavingPlansDistributionProcessor()

    result = processor.process(usage_result, journal_details, organization_invoice)

    assert result == []


def test_returns_empty_when_no_covered_usage(journal_details, organization_invoice):
    usage_result = _make_usage_result({
        "MPA-001": [_make_metric(AWSRecordTypeEnum.SAVING_PLAN_RECURRING_FEE, "1000")],
    })
    processor = SavingPlansDistributionProcessor()

    result = processor.process(usage_result, journal_details, organization_invoice)

    assert result == []


def test_sums_multiple_recurring_fee_metrics(journal_details, organization_invoice):
    usage_result = _make_usage_result({
        "MPA-001": [
            _make_metric(
                AWSRecordTypeEnum.SAVING_PLAN_RECURRING_FEE, "20000", "AWS Compute Savings Plans"
            ),
            _make_metric(
                AWSRecordTypeEnum.SAVING_PLAN_RECURRING_FEE, "16000", "AWS EC2 Savings Plans"
            ),
        ],
        "ACC-A": [_make_metric(AWSRecordTypeEnum.SAVING_PLAN_COVERED_USAGE, "1")],
    })
    processor = SavingPlansDistributionProcessor()

    result = processor.process(usage_result, journal_details, organization_invoice)

    assert len(result) == 1
    assert result[0].price.pp_x1 == Decimal("36000.00")


def test_skips_account_when_distributed_amount_rounds_to_zero(
    journal_details, organization_invoice
):
    """Covers the `if amount == DEC_ZERO: continue` branch."""
    usage_result = _make_usage_result({
        "MPA-001": [_make_metric(AWSRecordTypeEnum.SAVING_PLAN_RECURRING_FEE, "1")],
        "ACC-A": [_make_metric(AWSRecordTypeEnum.SAVING_PLAN_COVERED_USAGE, "1000000")],
        "ACC-B": [
            _make_metric(AWSRecordTypeEnum.SAVING_PLAN_COVERED_USAGE, "0.000001"),
        ],
    })
    processor = SavingPlansDistributionProcessor()

    result = processor.process(usage_result, journal_details, organization_invoice)

    account_ids = [line.search.source.criteria_value for line in result]
    assert "ACC-A" in account_ids
    assert "ACC-B" not in account_ids
