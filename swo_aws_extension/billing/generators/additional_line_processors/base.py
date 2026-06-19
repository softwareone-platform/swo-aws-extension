from abc import ABC, abstractmethod
from decimal import Decimal

from swo_aws_extension.billing.models.invoice import OrganizationInvoice
from swo_aws_extension.billing.models.journal_line import (
    InvoiceDetails,
    JournalDetails,
    JournalLine,
)
from swo_aws_extension.billing.models.usage import OrganizationUsageResult
from swo_aws_extension.constants import ItemSkuEnum


class AdditionalLineProcessor(ABC):
    """Base for processors that add journal lines after the main per-account usage pass."""

    item_sku: str = ItemSkuEnum.ADDITIONAL_CHARGES_SKU
    is_organization_charge: bool = False

    @abstractmethod
    def process(
        self,
        agreement: dict,
        usage_result: OrganizationUsageResult,
        journal_details: JournalDetails,
        organization_invoice: OrganizationInvoice,
    ) -> list[JournalLine]:
        """Return additional journal lines for the given agreement and usage data."""

    def _calculate_percentage_amount(self, base_amount: Decimal, percentage: Decimal) -> Decimal:
        return round(base_amount * (percentage / Decimal(100)), 6)

    def _build_org_journal_line(
        self,
        service_name: str,
        amount: Decimal,
        journal_details: JournalDetails,
        organization_invoice: OrganizationInvoice,
    ) -> JournalLine:
        invoice_details = InvoiceDetails(
            service_name=service_name,
            amount=amount,
            account_id=journal_details.mpa_id,
            invoice_entity=organization_invoice.primary_entity_name,
            invoice_id=organization_invoice.primary_invoice_id,
            start_date=journal_details.start_date,
            end_date=journal_details.end_date,
        )
        return JournalLine.build(
            self.item_sku,
            journal_details,
            invoice_details,
            is_organization_charge=self.is_organization_charge,
        )
