from dataclasses import dataclass
from decimal import Decimal
from typing import override

from swo_aws_extension.billing.generators.additional_line_processors.base import (
    AdditionalLineProcessor,
)
from swo_aws_extension.billing.generators.currency import resolve_service_amount
from swo_aws_extension.billing.models.invoice import OrganizationInvoice
from swo_aws_extension.billing.models.journal_line import (
    InvoiceDetails,
    JournalDetails,
    JournalLine,
)
from swo_aws_extension.billing.models.usage import OrganizationUsageResult, ServiceMetric
from swo_aws_extension.constants import DEC_ZERO, AWSRecordTypeEnum, ItemSkuEnum
from swo_aws_extension.logger import get_logger

logger = get_logger(__name__)


@dataclass
class _SPFeeData:
    total: Decimal
    service_name: str
    invoice_entity: str
    invoice_id: str


class SavingPlansDistributionProcessor(AdditionalLineProcessor):
    """Distribute org-level Saving Plans recurring fee to linked accounts by covered usage share.

    Only runs when split billing is enabled (splitBillingPolicy=LINKED_ACCOUNT_PERCENTAGE).
    Under MASTER_PAYER, SAVING_PLAN_RECURRING_FEE is handled by the normal line processor.

    AWS reports three Saving Plans record types:
      - SavingsPlanRecurringFee  (org level)  — the actual cost to distribute
      - SavingsPlanCoveredUsage  (per account) — positive weight for proportional split
      - SavingsPlanNegation      (per account) — cancels CoveredUsage in AWS totals; ignored here
    """

    item_sku: str = ItemSkuEnum.USAGE_SKU

    @override
    def process(
        self,
        agreement: dict,
        usage_result: OrganizationUsageResult,
        journal_details: JournalDetails,
        organization_invoice: OrganizationInvoice,
    ) -> list[JournalLine]:
        """Return one journal line per linked account with non-zero covered SP usage."""
        if not journal_details.split_billing_enabled:
            return []

        fee_data = self._collect_recurring_fee(usage_result, organization_invoice)
        if fee_data.total == DEC_ZERO:
            logger.info("No Saving Plans recurring fee found; skipping SP distribution.")
            return []

        covered_by_account = self._collect_covered_usage(usage_result)
        if not covered_by_account:
            logger.info("No Saving Plans covered usage found; skipping SP distribution.")
            return []

        total_covered = sum(covered_by_account.values(), DEC_ZERO)
        return self._build_distribution_lines(
            covered_by_account, total_covered, fee_data, journal_details
        )

    def _collect_recurring_fee(
        self,
        usage_result: OrganizationUsageResult,
        organization_invoice: OrganizationInvoice,
    ) -> _SPFeeData:
        """Sum all SAVING_PLAN_RECURRING_FEE metrics and return fee metadata."""
        metrics = self._get_sp_recurring_metrics(usage_result)
        if not metrics:
            return _SPFeeData(DEC_ZERO, "", "", "")
        return _SPFeeData(
            total=sum(
                (
                    resolve_service_amount(
                        metric.amount,
                        organization_invoice.entities.get(metric.invoice_entity or ""),
                    )
                    for metric in metrics
                ),
                DEC_ZERO,
            ),
            service_name=metrics[0].service_name,
            invoice_entity=metrics[0].invoice_entity or "",
            invoice_id=metrics[0].invoice_id or "",
        )

    def _get_sp_recurring_metrics(
        self, usage_result: OrganizationUsageResult
    ) -> list[ServiceMetric]:
        return [
            metric
            for account_usage in usage_result.usage_by_account.values()
            for metric in account_usage.get_metrics_by_record_type(
                AWSRecordTypeEnum.SAVING_PLAN_RECURRING_FEE
            )
        ]

    def _collect_covered_usage(self, usage_result: OrganizationUsageResult) -> dict[str, Decimal]:
        """Return covered SP usage per account (only accounts with positive covered usage)."""
        covered: dict[str, Decimal] = {}
        for account_id, account_usage in usage_result.usage_by_account.items():
            amount = sum(
                (
                    metric.amount
                    for metric in account_usage.get_metrics_by_record_type(
                        AWSRecordTypeEnum.SAVING_PLAN_COVERED_USAGE
                    )
                ),
                DEC_ZERO,
            )
            if amount > DEC_ZERO:
                covered[account_id] = amount
        return covered

    def _build_distribution_lines(
        self,
        covered_by_account: dict[str, Decimal],
        total_covered: Decimal,
        fee_data: _SPFeeData,
        journal_details: JournalDetails,
    ) -> list[JournalLine]:
        lines: list[JournalLine] = []
        for account_id, covered in covered_by_account.items():
            amount = round(fee_data.total * (covered / total_covered), 6)
            if amount == DEC_ZERO:
                continue
            logger.info(
                "Distributing %s SP fee to account %s (covered: %s / %s)",
                amount,
                account_id,
                covered,
                total_covered,
            )
            lines.append(self._build_line(account_id, amount, fee_data, journal_details))
        return lines

    def _build_line(
        self,
        account_id: str,
        amount: Decimal,
        fee_data: _SPFeeData,
        journal_details: JournalDetails,
    ) -> JournalLine:
        invoice_details = InvoiceDetails(
            service_name=fee_data.service_name,
            amount=amount,
            account_id=account_id,
            invoice_entity=fee_data.invoice_entity,
            invoice_id=fee_data.invoice_id,
            start_date=journal_details.start_date,
            end_date=journal_details.end_date,
        )
        return JournalLine.build(self.item_sku, journal_details, invoice_details)
