from decimal import Decimal

import pytest

from swo_aws_extension.constants import AWSRecordTypeEnum
from swo_aws_extension.flows.jobs.billing_journal.generators.pls_charge_manager import (
    PlSChargeManager,
)
from swo_aws_extension.flows.jobs.billing_journal.models.invoice import (
    InvoiceEntity,
    OrganizationInvoice,
)
from swo_aws_extension.flows.jobs.billing_journal.models.journal_line import JournalDetails
from swo_aws_extension.flows.jobs.billing_journal.models.usage import (
    AccountUsage,
    OrganizationReport,
    OrganizationUsageResult,
    ServiceMetric,
)


def create_metric(service_name, record_type, amount, invoice_entity="Entity1"):
    return ServiceMetric(
        service_name=service_name,
        record_type=record_type,
        amount=Decimal(amount),
        invoice_entity=invoice_entity,
        invoice_id="INV-123",
        start_date="2025-10-01",
        end_date="2025-10-31",
    )


def build_usage_result(metrics_by_account):
    return OrganizationUsageResult(
        reports=OrganizationReport(),
        usage_by_account={
            account_id: AccountUsage(metrics=metrics)
            for account_id, metrics in metrics_by_account.items()
        },
    )


@pytest.fixture
def organization_invoice():
    return OrganizationInvoice(
        principal_invoice_amount=Decimal("100.0"),
        entities={
            "Entity1": InvoiceEntity(
                invoice_id="INV-123",
                base_currency_code="USD",
                payment_currency_code="USD",
                exchange_rate=Decimal("1.0"),
            )
        },
    )


@pytest.fixture
def journal_details():
    return JournalDetails(
        agreement_id="AGR-1",
        mpa_id="MPA-1",
        start_date="2023-11-01",
        end_date="2023-11-30",
    )


def test_process_with_custom_percentage(journal_details, organization_invoice):
    usage_result = build_usage_result({
        "ACC-1": [
            create_metric("EC2", AWSRecordTypeEnum.USAGE, "200.00"),
            create_metric("RDS", AWSRecordTypeEnum.USAGE, "100.00"),
        ],
    })
    manager = PlSChargeManager()

    result = manager.process(Decimal("10.0"), usage_result, journal_details, organization_invoice)

    assert len(result) == 1
    assert result[0].price.unit_pp == Decimal("30.0")
    assert result[0].description.value1 == "SWO Enterprise support for AWS"
    assert result[0].external_ids.vendor == "MPA-1"


def test_process_with_default_percentage(journal_details, organization_invoice):
    usage_result = build_usage_result({
        "ACC-1": [create_metric("EC2", AWSRecordTypeEnum.USAGE, "100.00")],
    })
    manager = PlSChargeManager()

    result = manager.process(Decimal("5.0"), usage_result, journal_details, organization_invoice)

    assert len(result) == 1
    assert result[0].price.unit_pp == Decimal("5.0")


def test_process_sums_across_multiple_accounts(journal_details, organization_invoice):
    usage_result = build_usage_result({
        "ACC-1": [create_metric("EC2", AWSRecordTypeEnum.USAGE, "100.00")],
        "ACC-2": [create_metric("RDS", AWSRecordTypeEnum.USAGE, "100.00")],
    })
    manager = PlSChargeManager()

    result = manager.process(Decimal("10.0"), usage_result, journal_details, organization_invoice)

    assert len(result) == 1
    assert result[0].price.unit_pp == Decimal("20.0")


def test_process_returns_empty_when_zero_percentage(journal_details, organization_invoice):
    usage_result = build_usage_result({
        "ACC-1": [create_metric("EC2", AWSRecordTypeEnum.USAGE, "100.00")],
    })
    manager = PlSChargeManager()

    result = manager.process(Decimal("0.0"), usage_result, journal_details, organization_invoice)

    assert len(result) == 0


def test_process_returns_empty_when_no_usage(journal_details, organization_invoice):
    usage_result = build_usage_result({"ACC-1": []})
    manager = PlSChargeManager()

    result = manager.process(Decimal("5.0"), usage_result, journal_details, organization_invoice)

    assert len(result) == 0


def test_process_only_sums_usage_record_type(journal_details, organization_invoice):
    usage_result = build_usage_result({
        "ACC-1": [
            create_metric("EC2", AWSRecordTypeEnum.USAGE, "100.00"),
            create_metric("Support", AWSRecordTypeEnum.SUPPORT, "50.00"),
            create_metric("EC2", AWSRecordTypeEnum.CREDIT, "-10.00"),
            create_metric("EC2", AWSRecordTypeEnum.RECURRING, "20.00"),
        ],
    })
    manager = PlSChargeManager()

    result = manager.process(Decimal("5.0"), usage_result, journal_details, organization_invoice)

    assert len(result) == 1
    assert result[0].price.unit_pp == Decimal("5.0")


def test_process_applies_exchange_rate(journal_details):
    invoice = OrganizationInvoice(
        principal_invoice_amount=Decimal("100.0"),
        entities={
            "AWS EMEA": InvoiceEntity(
                invoice_id="INV-001",
                base_currency_code="USD",
                payment_currency_code="EUR",
                exchange_rate=Decimal("0.90"),
            )
        },
    )
    usage_result = build_usage_result({
        "ACC-1": [create_metric("EC2", AWSRecordTypeEnum.USAGE, "100.00", "AWS EMEA")],
    })
    manager = PlSChargeManager()

    result = manager.process(Decimal("5.0"), usage_result, journal_details, invoice)

    assert len(result) == 1
    assert result[0].price.unit_pp == Decimal("4.5")


def test_process_returns_empty_when_invoice_amount_is_zero(journal_details, organization_invoice):
    organization_invoice.principal_invoice_amount = Decimal(0)
    usage_result = build_usage_result({
        "ACC-1": [create_metric("EC2", AWSRecordTypeEnum.USAGE, "100.00")],
    })
    manager = PlSChargeManager()

    result = manager.process(Decimal("5.0"), usage_result, journal_details, organization_invoice)

    assert len(result) == 0
