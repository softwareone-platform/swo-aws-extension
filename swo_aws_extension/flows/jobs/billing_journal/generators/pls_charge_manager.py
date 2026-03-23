from decimal import Decimal

from swo_aws_extension.constants import (
    DEC_ZERO,
    AWSRecordTypeEnum,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.currency import (
    resolve_service_amount,
)
from swo_aws_extension.flows.jobs.billing_journal.models.invoice import OrganizationInvoice
from swo_aws_extension.flows.jobs.billing_journal.models.journal_line import (
    InvoiceDetails,
    JournalDetails,
    JournalLine,
)
from swo_aws_extension.flows.jobs.billing_journal.models.usage import (
    OrganizationUsageResult,
)
from swo_aws_extension.logger import get_logger

ITEM_SKU = "AWS Usage"
logger = get_logger(__name__)


class PlSChargeManager:
    """Manager to calculate and generate SWO Enterprise Support for AWS (PLS) charges."""

    def __init__(self) -> None:
        self._service_name = "SWO Enterprise support for AWS"

    def process(
        self,
        charge_percentage: Decimal,
        usage_result: OrganizationUsageResult,
        journal_details: JournalDetails,
        organization_invoice: OrganizationInvoice,
    ) -> list[JournalLine]:
        """Process PLS charge and return journal lines.

        Args:
            charge_percentage: The PLS percentage scalar to compute the charge.
            usage_result: The global organization usage result.
            journal_details: Shared journal details containing the MPA ID.
            organization_invoice: The organization invoice.

        Returns:
            List containing the PLS Charge journal line, if applicable.
        """
        principal_amount = organization_invoice.principal_invoice_amount
        if principal_amount is None or principal_amount == DEC_ZERO:
            return []

        if charge_percentage <= DEC_ZERO:
            return []

        base_amount = self._calculate_base_amount(usage_result, organization_invoice)
        if base_amount <= DEC_ZERO:
            return []

        charge_amount = self._calculate_charge_amount(base_amount, charge_percentage)

        invoice_details = InvoiceDetails(
            item_sku=ITEM_SKU,
            service_name=self._service_name,
            amount=charge_amount,
            account_id=journal_details.mpa_id,
            invoice_entity="",
            invoice_id="invoice_id",
        )
        return [JournalLine.build(ITEM_SKU, journal_details, invoice_details)]

    def _calculate_base_amount(
        self,
        usage_result: OrganizationUsageResult,
        organization_invoice: OrganizationInvoice,
    ) -> Decimal:
        total = DEC_ZERO
        for account_usage in usage_result.usage_by_account.values():
            usage_metrics = list(account_usage.get_metrics_by_record_type(AWSRecordTypeEnum.USAGE))
            total += sum(
                resolve_service_amount(
                    metric.amount,
                    organization_invoice.entities.get(metric.invoice_entity or ""),
                )
                for metric in usage_metrics
            )
        return total

    def _calculate_charge_amount(self, base_amount: Decimal, percentage: Decimal) -> Decimal:
        charge = base_amount * (percentage / Decimal(100))
        return round(charge, 6)
