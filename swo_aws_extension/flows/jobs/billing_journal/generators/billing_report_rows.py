from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, TypedDict

from swo_aws_extension.constants import DEC_ZERO, AWSRecordTypeEnum
from swo_aws_extension.flows.jobs.billing_journal.models.invoice import OrganizationInvoice
from swo_aws_extension.flows.jobs.billing_journal.models.journal_result import BillingReportRow
from swo_aws_extension.flows.jobs.billing_journal.models.usage import (
    OrganizationUsageResult,
    ServiceMetric,
)
from swo_aws_extension.logger import get_logger

if TYPE_CHECKING:
    from swo_aws_extension.flows.jobs.billing_journal.models.context import (
        AuthorizationContext,
    )
    from swo_aws_extension.flows.jobs.billing_journal.models.journal_line import JournalDetails

logger = get_logger(__name__)


class ServiceAmounts(TypedDict):
    """Accumulated amounts for a (service, invoice_id, invoice_entity) group."""

    amount: Decimal
    spp_discount: Decimal


@dataclass
class ReportContext:
    """Holding specific metrics report mapping variables."""

    authorization_id: str
    pma: str
    agreement_id: str
    mpa: str
    currency: str

    @classmethod
    def from_contexts(
        cls,
        auth_context: "AuthorizationContext",
        journal_details: "JournalDetails",
    ) -> "ReportContext":
        """Build a ReportContext from existing auth and journal contexts."""
        return cls(
            authorization_id=auth_context.id,
            pma=auth_context.pma_account,
            agreement_id=journal_details.agreement_id,
            mpa=journal_details.mpa_id,
            currency=auth_context.currency,
        )


type ReportGroupsAlias = dict[tuple[str, str, str], ServiceAmounts]


def _process_metrics(
    metrics: list[ServiceMetric],
    groups: ReportGroupsAlias,
) -> None:
    for metric in metrics:
        key = (metric.service_name, metric.invoice_id or "", metric.invoice_entity or "")
        if key not in groups:
            groups[key] = ServiceAmounts(amount=DEC_ZERO, spp_discount=DEC_ZERO)

        if metric.record_type == AWSRecordTypeEnum.SOLUTION_PROVIDER_PROGRAM_DISCOUNT:
            groups[key]["spp_discount"] += metric.amount
        else:
            groups[key]["amount"] += metric.amount


def _group_service_metrics(
    usage_result: OrganizationUsageResult,
) -> ReportGroupsAlias:
    groups: ReportGroupsAlias = {}
    for account_usage in usage_result.usage_by_account.values():
        _process_metrics(account_usage.metrics, groups)
    return groups


def _resolve_exchange_rate(inv_entity: str, org_invoice: OrganizationInvoice) -> Decimal:
    if inv_entity and inv_entity in org_invoice.entities:
        return org_invoice.entities[inv_entity].exchange_rate
    if inv_entity:
        logger.warning(
            "No exchange rate found for invoice entity '%s'. Defaulting to 1.0",
            inv_entity,
        )
    return Decimal("1.0")


def generate_billing_report_rows(
    context: ReportContext,
    usage_result: OrganizationUsageResult,
    organization_invoice: OrganizationInvoice,
) -> list[BillingReportRow]:
    """Aggregate usage metrics into distinct billing report rows."""
    groups = _group_service_metrics(usage_result)

    return [
        BillingReportRow(
            authorization_id=context.authorization_id,
            pma=context.pma,
            agreement_id=context.agreement_id,
            mpa=context.mpa,
            service_name=service_name,
            amount=amounts["amount"],
            currency=context.currency,
            invoice_id=inv_id,
            invoice_entity=inv_entity,
            exchange_rate=_resolve_exchange_rate(inv_entity, organization_invoice),
            spp_discount=amounts["spp_discount"],
        )
        for (service_name, inv_id, inv_entity), amounts in groups.items()
    ]
