from decimal import Decimal

from swo_aws_extension.constants import AWSRecordTypeEnum
from swo_aws_extension.flows.jobs.billing_journal.models.invoice import (
    InvoiceEntity,
    OrganizationInvoice,
)
from swo_aws_extension.flows.jobs.billing_journal.models.usage import (
    AccountUsage,
    OrganizationReport,
    OrganizationUsageResult,
    ServiceMetric,
)
from swo_aws_extension.flows.jobs.billing_validation.usage_split import build_service_split

ENTITY = "Amazon Web Services EMEA SARL:AWS"
SPP = AWSRecordTypeEnum.SOLUTION_PROVIDER_PROGRAM_DISCOUNT


def _metric(service, record_type, amount):
    return ServiceMetric(
        service_name=service,
        record_type=record_type,
        start_date="2026-09-01",
        end_date="2026-09-30",
        amount=Decimal(amount),
        invoice_entity=ENTITY,
    )


def _usage_result():
    account = AccountUsage(
        metrics=[
            _metric("Amazon EC2", AWSRecordTypeEnum.USAGE, "1000"),
            _metric("Amazon EC2", SPP, "-80"),
            _metric("Savings Plans for AWS Compute usage", "SavingsPlanRecurringFee", "500"),
            _metric("Savings Plans for AWS Compute usage", SPP, "-40"),
            _metric("AWS Support (Enterprise)", AWSRecordTypeEnum.SUPPORT, "206.11"),
            _metric("AWS Support (Enterprise)", SPP, "-82.45"),
            _metric("AWS Support (Business)", AWSRecordTypeEnum.SUPPORT, "100"),
            _metric("AWS Support (Business)", SPP, "-7"),
            _metric("Tax", "Tax", "50"),
        ]
    )
    return OrganizationUsageResult(
        reports=OrganizationReport(), usage_by_account={"ACC-1": account}
    )


def test_build_service_split_groups_support_and_usage():
    result = build_service_split(_usage_result(), OrganizationInvoice())

    assert result.enterprise_support_charge == Decimal("206.11")
    assert result.enterprise_support_spp == Decimal("-82.45")
    assert (result.resold_support_charge, result.resold_support_spp) == (
        Decimal(100),
        Decimal(-7),
    )
    assert result.usage_base == Decimal(1000)
    assert result.support_spp == Decimal("-89.45")


def test_build_service_split_converts_to_payment_currency():
    invoice = OrganizationInvoice(
        entities={
            ENTITY: InvoiceEntity(
                base_currency_code="USD", payment_currency_code="EUR", exchange_rate=Decimal("0.5")
            )
        }
    )

    result = build_service_split(_usage_result(), invoice)

    assert result.usage_base == Decimal("500.0")
    assert result.enterprise_support_charge == Decimal("103.055")
