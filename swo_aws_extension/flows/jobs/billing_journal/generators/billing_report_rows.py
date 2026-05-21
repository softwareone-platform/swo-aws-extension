from dataclasses import dataclass
from decimal import Decimal
from itertools import starmap
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


class BillingReportRowsBuilder:
    """Builds billing report rows from usage metrics and invoice data."""

    def __init__(
        self,
        context: ReportContext,
        usage_result: OrganizationUsageResult,
        organization_invoice: OrganizationInvoice,
    ):
        self._context = context
        self._usage_result = usage_result
        self._invoice = organization_invoice

    def build(self) -> list[BillingReportRow]:
        """Aggregate usage metrics into distinct billing report rows."""
        groups: dict[tuple[str, str, str], ServiceAmounts] = {}
        for account_usage in self._usage_result.usage_by_account.values():
            for metric in account_usage.metrics:
                key = (metric.service_name, metric.invoice_id or "", metric.invoice_entity or "")
                self._accumulate(groups, key, metric)
        return list(starmap(self._to_row, groups.items()))

    def build_by_account(self) -> list[BillingReportRow]:
        """Build billing report rows broken down by linked account."""
        return [
            self._to_row(
                (service_name, inv_id, inv_entity),
                amounts,
                linked_account=account_id,
            )
            for (
                account_id,
                service_name,
                inv_id,
                inv_entity,
            ), amounts in self._group_by_account().items()
        ]

    def _group_by_account(self) -> dict[tuple[str, str, str, str], ServiceAmounts]:
        groups: dict[tuple[str, str, str, str], ServiceAmounts] = {}
        for account_id, account_usage in self._usage_result.usage_by_account.items():
            for metric in account_usage.metrics:
                key = (
                    account_id,
                    metric.service_name,
                    metric.invoice_id or "",
                    metric.invoice_entity or "",
                )
                self._accumulate(groups, key, metric)
        return groups

    def _accumulate(self, groups: dict, key: tuple, metric: ServiceMetric) -> None:
        if key not in groups:
            groups[key] = ServiceAmounts(amount=DEC_ZERO, spp_discount=DEC_ZERO)
        if metric.record_type == AWSRecordTypeEnum.SOLUTION_PROVIDER_PROGRAM_DISCOUNT:
            groups[key]["spp_discount"] += metric.amount
        else:
            groups[key]["amount"] += metric.amount

    def _to_row(
        self,
        metric_key: tuple,
        amounts: ServiceAmounts,
        linked_account: str = "",
    ) -> BillingReportRow:
        service_name, inv_id, inv_entity = metric_key
        exchange_rate = self._resolve_exchange_rate(inv_entity)
        spp_discount_pct = (
            abs(amounts["spp_discount"]) / amounts["amount"] if amounts["amount"] else DEC_ZERO
        )
        return BillingReportRow(
            authorization_id=self._context.authorization_id,
            pma=self._context.pma,
            agreement_id=self._context.agreement_id,
            mpa=self._context.mpa,
            service_name=service_name,
            pp=(amounts["amount"] - abs(amounts["spp_discount"])) * exchange_rate,
            sp=amounts["amount"] * exchange_rate,
            currency=self._context.currency,
            invoice_id=inv_id,
            invoice_entity=inv_entity,
            exchange_rate=exchange_rate,
            spp_discount=amounts["spp_discount"] * exchange_rate,
            spp_discount_pct=spp_discount_pct,
            linked_account=linked_account,
        )

    def _resolve_exchange_rate(self, inv_entity: str) -> Decimal:
        if inv_entity and inv_entity in self._invoice.entities:
            rate = self._invoice.entities[inv_entity].exchange_rate
            return rate if rate > DEC_ZERO else Decimal("1.0")
        return Decimal("1.0")
