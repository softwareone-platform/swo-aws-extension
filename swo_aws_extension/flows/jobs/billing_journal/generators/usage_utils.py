from decimal import Decimal

from swo_aws_extension.constants import DEC_ZERO
from swo_aws_extension.flows.jobs.billing_journal.generators.currency import resolve_service_amount
from swo_aws_extension.flows.jobs.billing_journal.models.invoice import OrganizationInvoice
from swo_aws_extension.flows.jobs.billing_journal.models.usage import OrganizationUsageResult


def calculate_total_by_record_types(
    usage_result: OrganizationUsageResult,
    organization_invoice: OrganizationInvoice,
    record_types: set[str],
) -> Decimal:
    """Calculate the total service amount for specific record types across the organization."""
    total = DEC_ZERO
    for account_usage in usage_result.usage_by_account.values():
        for metric in account_usage.metrics:
            if metric.record_type in record_types:
                total += resolve_service_amount(
                    metric.amount,
                    organization_invoice.entities.get(metric.invoice_entity or ""),
                )
    return total
