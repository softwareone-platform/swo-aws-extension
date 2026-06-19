from decimal import Decimal

from swo_aws_extension.billing.generators.usage_utils import calculate_total_by_record_types
from swo_aws_extension.billing.models.invoice import OrganizationInvoice
from swo_aws_extension.billing.models.journal_line import (
    InvoiceDetails,
    JournalDetails,
    JournalLine,
)
from swo_aws_extension.billing.models.usage import OrganizationUsageResult
from swo_aws_extension.constants import DEC_ZERO, AWSRecordTypeEnum, ItemSkuEnum
from swo_aws_extension.logger import get_logger

logger = get_logger(__name__)


class PlSChargeProcessor:
    """Processor to calculate and generate SWO Enterprise Support for AWS (PLS) charges."""

    item_sku: str = ItemSkuEnum.ADDITIONAL_CHARGES_SKU
    is_organization_charge: bool = True

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
        logger.info("Processing '%s' charge with %s", self._service_name, charge_percentage)
        principal_amount = organization_invoice.principal_invoice_amount
        if principal_amount == DEC_ZERO:
            return []

        if charge_percentage <= DEC_ZERO:
            return []

        base_amount = self._calculate_base_amount(usage_result, organization_invoice)
        logger.info("Usage amount: %s", base_amount)
        if base_amount <= DEC_ZERO:
            return []

        charge_amount = self._calculate_charge_amount(base_amount, charge_percentage)
        logger.info("PLS Charge amount: %s ", charge_amount)

        invoice_details = InvoiceDetails(
            service_name=self._service_name,
            amount=charge_amount,
            account_id=journal_details.mpa_id,
            invoice_entity=organization_invoice.primary_entity_name,
            invoice_id=organization_invoice.primary_invoice_id,
            start_date=journal_details.start_date,
            end_date=journal_details.end_date,
        )
        return [
            JournalLine.build(
                self.item_sku,
                journal_details,
                invoice_details,
                is_organization_charge=self.is_organization_charge,
            )
        ]

    def _calculate_base_amount(
        self,
        usage_result: OrganizationUsageResult,
        organization_invoice: OrganizationInvoice,
    ) -> Decimal:
        return calculate_total_by_record_types(
            usage_result,
            organization_invoice,
            {AWSRecordTypeEnum.USAGE},
        )

    def _calculate_charge_amount(self, base_amount: Decimal, percentage: Decimal) -> Decimal:
        charge = base_amount * (percentage / Decimal(100))
        return round(charge, 6)
