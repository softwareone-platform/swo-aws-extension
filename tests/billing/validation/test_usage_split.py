from decimal import Decimal

from swo_aws_extension.billing.models.invoice import (
    InvoiceEntity,
    OrganizationInvoice,
)
from swo_aws_extension.billing.models.usage import (
    AccountUsage,
    OrganizationReport,
    OrganizationUsageResult,
    ServiceMetric,
)
from swo_aws_extension.billing.validation.usage_split import build_service_split
from swo_aws_extension.constants import AWSRecordTypeEnum

ENTITY = "Amazon Web Services EMEA SARL:AWS"
SPP = AWSRecordTypeEnum.SOLUTION_PROVIDER_PROGRAM_DISCOUNT
# usage (1000) plus the Savings Plan recurring fee (500) and the recurring charge (200),
# net of the bundled discount (-100)
USAGE_BASE = Decimal("1600.0")


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
            _metric("Amazon RDS", AWSRecordTypeEnum.RECURRING, "200"),
            _metric("Amazon RDS", SPP, "-16"),
            _metric("AmazonCloudWatch", AWSRecordTypeEnum.BUNDLE_DISCOUNT, "-100"),
            _metric("Amazon EC2", AWSRecordTypeEnum.REFUND, "-30"),
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
    assert result.usage_base == USAGE_BASE
    assert result.support_spp == Decimal("-89.45")


def test_build_service_split_usage_base_adds_recurring_fees_net_of_bundled_discount():
    result = build_service_split(_usage_result(), OrganizationInvoice())

    # support, SPP, refunds and tax stay out, as in the journal
    assert result.usage_base == USAGE_BASE


def test_build_service_split_converts_to_payment_currency():
    invoice = OrganizationInvoice(
        entities={
            ENTITY: InvoiceEntity(
                base_currency_code="USD", payment_currency_code="EUR", exchange_rate=Decimal("0.5")
            )
        }
    )

    result = build_service_split(_usage_result(), invoice)

    assert result.usage_base == Decimal("800.0")
    assert result.enterprise_support_charge == Decimal("103.055")
