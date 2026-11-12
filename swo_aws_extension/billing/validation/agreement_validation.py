"""Validate one agreement of a billing journal run against its AWS invoices.

Everything the validation needs is already in memory when the journal lines of an
agreement are generated: the raw invoice summaries, the agreement parameters, the
Cost Explorer usage and the SPP summary row. This module wires them together so the
journal generator can emit a validation per agreement without extra API calls.
"""

from decimal import Decimal

from swo_aws_extension.billing.models.invoice import OrganizationInvoiceResult
from swo_aws_extension.billing.models.journal_result import (
    OrganizationSppSummaryRow,
)
from swo_aws_extension.billing.models.usage import OrganizationUsageResult
from swo_aws_extension.billing.validation.agreements import (
    extract_discounts,
    extract_info,
)
from swo_aws_extension.billing.validation.calculator import ExpectedBillingCalculator
from swo_aws_extension.billing.validation.invoice_mapper import InvoiceMapper
from swo_aws_extension.billing.validation.results import (
    AgreementValidation,
    ExpectedBilling,
)
from swo_aws_extension.billing.validation.usage_split import build_service_split
from swo_aws_extension.billing.validation.validator import (
    DEFAULT_TOLERANCE,
    BillingValidator,
)
from swo_aws_extension.logger import get_logger

logger = get_logger(__name__)


class AgreementBillingValidator:
    """Build the validation of one agreement from the data gathered by the journal."""

    def __init__(
        self,
        pls_charge_percentage: Decimal,
        tolerance: Decimal = DEFAULT_TOLERANCE,
        authorization_name: str = "",
    ) -> None:
        self._calculator = ExpectedBillingCalculator(pls_charge_percentage)
        self._validator = BillingValidator(tolerance)
        self._authorization_name = authorization_name

    def validate(
        self,
        agreement: dict,
        usage_result: OrganizationUsageResult,
        invoice_result: OrganizationInvoiceResult,
        spp_summary_row: OrganizationSppSummaryRow | None,
    ) -> AgreementValidation | None:
        """Compare the SPP summary row of the agreement with the manual validation rules.

        The validation is informative, so any unexpected error is logged and reported
        as an ``ERROR`` validation instead of blocking the journal generation.

        Args:
            agreement: Agreement payload including its parameters.
            usage_result: Cost Explorer usage of the organization.
            invoice_result: Raw and processed AWS invoices of the MPA.
            spp_summary_row: Agreement level row produced by the journal generator.

        Returns:
            The validation with its checks, status and notes, or None when the
            agreement has no SPP summary row.
        """
        if spp_summary_row is None:
            return None
        try:
            return self._validate(agreement, usage_result, invoice_result, spp_summary_row)
        except Exception as error:
            logger.exception("Failed to validate the billing of agreement")
            return self._validator.unexpected_error(spp_summary_row, error)

    def _validate(
        self,
        agreement: dict,
        usage_result: OrganizationUsageResult,
        invoice_result: OrganizationInvoiceResult,
        spp_summary_row: OrganizationSppSummaryRow,
    ) -> AgreementValidation:
        invoices = InvoiceMapper(
            invoice_result.raw_data, spp_summary_row.currency, invoice_result.invoice
        ).for_mpa(spp_summary_row.mpa)
        names = extract_info(agreement, self._authorization_name)
        if not invoices.lines:
            validation = self._validator.missing_invoices(spp_summary_row)
            validation.names = names
            return validation

        expected = self._calculator.calculate(
            ExpectedBilling(
                agreement_id=spp_summary_row.agreement_id,
                mpa=spp_summary_row.mpa,
                pma=spp_summary_row.pma,
                authorization_id=spp_summary_row.authorization_id,
                currency=spp_summary_row.currency,
                names=names,
            ),
            invoices,
            extract_discounts(agreement),
            build_service_split(usage_result, invoice_result.invoice),
        )
        validation = self._validator.validate(expected, spp_summary_row)
        _log_validation(validation)
        return validation


def _log_validation(validation: AgreementValidation) -> None:
    if not validation.failed_checks and not validation.notes:
        logger.info("Billing validation OK")
        return
    details = "; ".join(
        f"{check.name}: expected {check.expected:.2f}, platform {check.actual:.2f}"
        for check in validation.failed_checks
    )
    logger.warning(
        "Billing validation %s %s %s %s",
        validation.status.value,
        details,
        validation.likely_cause,
        " | ".join(validation.notes),
    )
