"""Split the Cost Explorer usage into the amounts the invoice summary does not carry."""

from swo_aws_extension.constants import AWSRecordTypeEnum
from swo_aws_extension.flows.jobs.billing_journal.generators.currency import (
    resolve_service_amount,
)
from swo_aws_extension.flows.jobs.billing_journal.models.invoice import OrganizationInvoice
from swo_aws_extension.flows.jobs.billing_journal.models.usage import (
    OrganizationUsageResult,
    ServiceMetric,
)
from swo_aws_extension.flows.jobs.billing_validation.models import ServiceSplit

ENTERPRISE_SUPPORT_SERVICE = "AWS Support (Enterprise)"


def build_service_split(
    usage_result: OrganizationUsageResult,
    organization_invoice: OrganizationInvoice,
) -> ServiceSplit:
    """Aggregate support charges, their SPP discount and the usage base per organization.

    Amounts are converted to the agreement currency with the same rule the journal
    lines use, so the split can be combined with the invoice totals.
    """
    split = ServiceSplit()
    for account_usage in usage_result.usage_by_account.values():
        support_services = {
            metric.service_name
            for metric in account_usage.get_metrics_by_record_type(AWSRecordTypeEnum.SUPPORT)
        }
        for metric in account_usage.metrics:
            _accumulate(split, metric, organization_invoice, support_services)
    return split


def _accumulate(
    split: ServiceSplit,
    metric: ServiceMetric,
    organization_invoice: OrganizationInvoice,
    support_services: set[str],
) -> None:
    amount = resolve_service_amount(
        metric.amount,
        organization_invoice.entities.get(metric.invoice_entity or ""),
    )
    if metric.record_type == AWSRecordTypeEnum.SUPPORT:
        _add_support(split, metric.service_name, amount)
    elif metric.record_type == AWSRecordTypeEnum.SOLUTION_PROVIDER_PROGRAM_DISCOUNT:
        _add_spp(split, metric.service_name, amount, support_services)
    elif metric.record_type == AWSRecordTypeEnum.USAGE:
        split.usage_base += amount


def _add_support(split: ServiceSplit, service_name: str, amount) -> None:
    if service_name == ENTERPRISE_SUPPORT_SERVICE:
        split.enterprise_support_charge += amount
    else:
        split.resold_support_charge += amount


def _add_spp(split: ServiceSplit, service_name: str, amount, support_services: set[str]) -> None:
    if service_name == ENTERPRISE_SUPPORT_SERVICE:
        split.enterprise_support_spp += amount
    elif service_name in support_services:
        split.resold_support_spp += amount
