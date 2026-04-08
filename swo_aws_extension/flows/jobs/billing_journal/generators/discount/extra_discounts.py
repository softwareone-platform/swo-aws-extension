from abc import ABC, abstractmethod
from decimal import Decimal
from typing import override

from swo_aws_extension.constants import (
    DEC_ZERO,
    AWSRecordTypeEnum,
    ChannelHandshakeDeployed,
    SupportTypesEnum,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.currency import (
    resolve_service_amount,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.usage_utils import (
    calculate_total_by_record_types,
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
from swo_aws_extension.parameters import (
    get_channel_handshake_approval_status,
    get_pls_discount,
    get_service_discount,
    get_support_discount,
    get_support_type,
)

ITEM_SKU = "AWS Usage"
logger = get_logger(__name__)


class BaseExtraDiscountProcessor(ABC):
    """Base class for all extra discounts processors."""

    def __init__(self, service_name: str) -> None:
        self._service_name = service_name

    def process(
        self,
        agreement: dict,
        usage_result: OrganizationUsageResult,
        journal_details: JournalDetails,
        organization_invoice: OrganizationInvoice,
    ) -> list[JournalLine]:
        """Process extra discount and return journal lines.

        Args:
            agreement: The agreement data containing the parameters.
            usage_result: The global organization usage result.
            journal_details: Shared journal details containing the MPA ID.
            organization_invoice: The organization invoice.

        Returns:
            List of journal lines containing the discount refund.
        """
        if not self._is_applicable(agreement):
            return []

        discount_percentage = self._get_discount_percentage(agreement)
        if not discount_percentage or discount_percentage <= DEC_ZERO:
            return []

        base_amount = self._calculate_base_amount(usage_result, organization_invoice)
        if base_amount == DEC_ZERO:
            return []

        refund_amount = self._calculate_refund_amount(base_amount, discount_percentage)

        invoice_details = InvoiceDetails(
            item_sku=ITEM_SKU,
            service_name=self._service_name,
            amount=refund_amount,
            account_id=journal_details.mpa_id,
            invoice_entity=organization_invoice.primary_entity_name,
            invoice_id=organization_invoice.primary_invoice_id,
            start_date=journal_details.start_date,
            end_date=journal_details.end_date,
        )
        return [JournalLine.build(ITEM_SKU, journal_details, invoice_details)]

    @abstractmethod
    def _is_applicable(self, agreement: dict) -> bool:
        """Check if this specific discount is applicable based on agreement parameters."""

    @abstractmethod
    def _get_discount_percentage(self, agreement: dict) -> Decimal:
        """Get the discount percentage configured in the agreement parameters."""

    @abstractmethod
    def _calculate_base_amount(
        self,
        usage_result: OrganizationUsageResult,
        organization_invoice: OrganizationInvoice,
    ) -> Decimal:
        """Calculate the sum of metrics over which the discount is applied."""

    def _calculate_refund_amount(self, base_amount: Decimal, percentage: Decimal) -> Decimal:
        refund = base_amount * (percentage / Decimal(100))
        return round(refund, 6)


class ServiceDiscountProcessor(BaseExtraDiscountProcessor):
    """Processor for Service Extra Discount."""

    def __init__(self) -> None:
        super().__init__(service_name="SWO additional Usage discount")

    @override
    def _is_applicable(self, agreement: dict) -> bool:
        return get_channel_handshake_approval_status(agreement) == ChannelHandshakeDeployed.YES

    @override
    def _get_discount_percentage(self, agreement: dict) -> Decimal:
        discount_value = get_service_discount(agreement)
        return Decimal(discount_value) if discount_value else DEC_ZERO

    @override
    def _calculate_base_amount(
        self,
        usage_result: OrganizationUsageResult,
        organization_invoice: OrganizationInvoice,
    ) -> Decimal:
        target_record_types = {
            AWSRecordTypeEnum.USAGE,
            AWSRecordTypeEnum.RECURRING,
            AWSRecordTypeEnum.SAVING_PLAN_RECURRING_FEE,
        }
        total = DEC_ZERO
        for account_usage in usage_result.usage_by_account.values():
            applicable_service_names = {
                metric.service_name
                for metric in account_usage.metrics
                if metric.record_type in target_record_types
            }

            spp_metrics = [
                metric
                for metric in account_usage.get_metrics_by_record_type(
                    AWSRecordTypeEnum.SOLUTION_PROVIDER_PROGRAM_DISCOUNT
                )
                if metric.service_name in applicable_service_names
            ]
            total += sum(
                resolve_service_amount(
                    metric.amount,
                    organization_invoice.entities.get(metric.invoice_entity or ""),
                )
                for metric in spp_metrics
            )
        return total


class SupportDiscountProcessor(BaseExtraDiscountProcessor):
    """Processor for Support Extra Discount."""

    def __init__(self) -> None:
        super().__init__(service_name="SWO additional Support discount")

    @override
    def _is_applicable(self, agreement: dict) -> bool:
        if get_channel_handshake_approval_status(agreement) != ChannelHandshakeDeployed.YES:
            return False
        return get_support_type(agreement) == SupportTypesEnum.AWS_RESOLD_SUPPORT

    @override
    def _get_discount_percentage(self, agreement: dict) -> Decimal:
        discount_value = get_support_discount(agreement)
        return Decimal(discount_value) if discount_value else DEC_ZERO

    @override
    def _calculate_base_amount(
        self,
        usage_result: OrganizationUsageResult,
        organization_invoice: OrganizationInvoice,
    ) -> Decimal:
        total = DEC_ZERO
        for account_usage in usage_result.usage_by_account.values():
            support_service_names = {
                metric.service_name
                for metric in account_usage.get_metrics_by_record_type(AWSRecordTypeEnum.SUPPORT)
            }
            spp_metrics = [
                metric
                for metric in account_usage.get_metrics_by_record_type(
                    AWSRecordTypeEnum.SOLUTION_PROVIDER_PROGRAM_DISCOUNT
                )
                if metric.service_name in support_service_names
            ]
            total += sum(
                resolve_service_amount(
                    metric.amount,
                    organization_invoice.entities.get(metric.invoice_entity or ""),
                )
                for metric in spp_metrics
            )
        return total


class PlSDiscountProcessor(BaseExtraDiscountProcessor):
    """Processor for PLS Extra Discount."""

    def __init__(self, charge_percentage: Decimal) -> None:
        super().__init__(service_name="SWO additional PLS Support discount")
        self._charge_percentage = charge_percentage

    @override
    def _is_applicable(self, agreement: dict) -> bool:
        if get_channel_handshake_approval_status(agreement) != ChannelHandshakeDeployed.YES:
            return False
        return get_support_type(agreement) == SupportTypesEnum.PARTNER_LED_SUPPORT

    @override
    def _get_discount_percentage(self, agreement: dict) -> Decimal:
        discount_value = get_pls_discount(agreement)
        return Decimal(discount_value) if discount_value else DEC_ZERO

    @override
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


class ExtraDiscountsManager:
    """Manager to process all extra discounts globally across an organization."""

    def __init__(self, pls_charge_percentage: Decimal) -> None:
        self._processors = [
            ServiceDiscountProcessor(),
            SupportDiscountProcessor(),
            PlSDiscountProcessor(pls_charge_percentage),
        ]

    def process(
        self,
        agreement: dict,
        usage_result: OrganizationUsageResult,
        journal_details: JournalDetails,
        organization_invoice: OrganizationInvoice,
    ) -> list[JournalLine]:
        """Apply all extra discounts over the organization usage result."""
        lines = []
        principal_amount = organization_invoice.principal_invoice_amount
        if principal_amount == DEC_ZERO:
            logger.info("Principal invoice amount is zero, skipping extra discounts processing.")
            return lines

        for processor in self._processors:
            lines.extend(
                processor.process(
                    agreement,
                    usage_result,
                    journal_details,
                    organization_invoice,
                )
            )
        return lines
