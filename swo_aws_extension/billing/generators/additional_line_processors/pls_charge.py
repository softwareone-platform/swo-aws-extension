from decimal import Decimal
from typing import override

from swo_aws_extension.billing.generators.additional_line_processors.base import (
    AdditionalLineProcessor,
)
from swo_aws_extension.billing.generators.usage_utils import calculate_total_by_record_types
from swo_aws_extension.billing.models.invoice import OrganizationInvoice
from swo_aws_extension.billing.models.journal_line import JournalDetails, JournalLine
from swo_aws_extension.billing.models.usage import OrganizationUsageResult
from swo_aws_extension.constants import DEC_ZERO, AWSRecordTypeEnum
from swo_aws_extension.logger import get_logger

logger = get_logger(__name__)


class PlSChargeProcessor(AdditionalLineProcessor):
    """Processor to calculate and generate SWO Enterprise Support for AWS (PLS) charges."""

    is_organization_charge: bool = True

    def __init__(self, charge_percentage: Decimal) -> None:
        self._service_name = "SWO Enterprise support for AWS"
        self._charge_percentage = charge_percentage

    @override
    def process(
        self,
        agreement: dict,
        usage_result: OrganizationUsageResult,
        journal_details: JournalDetails,
        organization_invoice: OrganizationInvoice,
    ) -> list[JournalLine]:
        if not usage_result.has_enterprise_support():
            return []

        logger.info("Processing '%s' charge with %s", self._service_name, self._charge_percentage)
        principal_amount = organization_invoice.principal_invoice_amount
        if principal_amount == DEC_ZERO:
            return []

        if self._charge_percentage <= DEC_ZERO:
            return []

        base_amount = self._calculate_base_amount(usage_result, organization_invoice)
        logger.info("Usage amount: %s", base_amount)
        if base_amount <= DEC_ZERO:
            return []

        charge_amount = self._calculate_percentage_amount(base_amount, self._charge_percentage)
        logger.info("PLS Charge amount: %s ", charge_amount)

        return [
            self._build_org_journal_line(
                self._service_name, charge_amount, journal_details, organization_invoice
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
