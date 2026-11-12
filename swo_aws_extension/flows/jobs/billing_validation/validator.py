"""Compare the expected billing against the platform results."""

from decimal import Decimal

from swo_aws_extension.flows.jobs.billing_journal.models.journal_result import (
    OrganizationSppSummaryRow,
)
from swo_aws_extension.flows.jobs.billing_validation.causes import explain_mismatch
from swo_aws_extension.flows.jobs.billing_validation.results import (
    AgreementValidation,
    CheckResult,
    ExpectedBilling,
    ValidationStatus,
)

DEFAULT_TOLERANCE = Decimal("0.05")
SALES_PRICE_CHECK = "Sales price (SP)"
COST_PRICE_CHECK = "Cost price (PP)"


class BillingValidator:
    """Build the validation result of one agreement.

    Two checks decide the status: the cost price (AWS invoices vs platform PP) and the
    sales price (manual operations vs platform SP). The list price, SPP discount and
    markup are reported for information only.

    The tolerance is expressed in USD and converted to the agreement currency with the
    exchange rate of the invoices, so 0.05 USD becomes roughly 800 IDR or 0.04 EUR.
    The SPP discount of the invoice (rounded by AWS per line) and the one reported by
    Cost Explorer legitimately differ by a few cents, so that difference is not held
    against the sales price.
    """

    def __init__(self, tolerance: Decimal = DEFAULT_TOLERANCE) -> None:
        self._tolerance = tolerance

    def validate(
        self,
        expected: ExpectedBilling,
        platform: OrganizationSppSummaryRow | None,
    ) -> AgreementValidation:
        """Compare cost price and sales price within the tolerance."""
        validation = AgreementValidation(
            agreement_id=expected.agreement_id,
            mpa=expected.mpa,
            pma=expected.pma,
            authorization_id=expected.authorization_id,
            currency=expected.currency,
            status=ValidationStatus.OK,
            expected=expected,
            platform=platform,
            notes=list(expected.notes),
            names=expected.names,
        )
        if platform is None:
            validation.status = ValidationStatus.MISSING_IN_PLATFORM
            validation.likely_cause = "No SPP Summary row was produced for the agreement."
            return validation

        tolerance = self._tolerance * self._exchange_rate(expected, platform)
        spp_source_diff = abs(platform.spp_discount - expected.spp_discount)
        validation.tolerance = tolerance
        validation.checks = [
            CheckResult(COST_PRICE_CHECK, expected.cost_price, platform.pp, tolerance),
            CheckResult(
                SALES_PRICE_CHECK,
                expected.sales_price,
                platform.sp,
                tolerance + spp_source_diff,
            ),
        ]
        if spp_source_diff > tolerance:
            validation.notes.append(
                f"SPP discount differs between the AWS invoice and Cost Explorer by "
                f"{spp_source_diff:.2f} {platform.currency} (AWS rounding); the sales price "
                "tolerance was widened by that amount."
            )
        if validation.failed_checks:
            validation.status = ValidationStatus.MISMATCH
            validation.likely_cause = explain_mismatch(validation)
        return validation

    def missing_invoices(self, platform: OrganizationSppSummaryRow) -> AgreementValidation:
        """Build the result for a platform row without AWS invoices."""
        return AgreementValidation(
            agreement_id=platform.agreement_id,
            mpa=platform.mpa,
            pma=platform.pma,
            authorization_id=platform.authorization_id,
            currency=platform.currency,
            status=ValidationStatus.MISSING_INVOICES,
            platform=platform,
            likely_cause="No AWS invoices found for the MPA account.",
        )

    def unexpected_error(
        self, platform: OrganizationSppSummaryRow, error: Exception
    ) -> AgreementValidation:
        """Build the result for a platform row whose validation raised an error."""
        return AgreementValidation(
            agreement_id=platform.agreement_id,
            mpa=platform.mpa,
            pma=platform.pma,
            authorization_id=platform.authorization_id,
            currency=platform.currency,
            status=ValidationStatus.ERROR,
            platform=platform,
            notes=[f"{type(error).__name__}: {error}"],
            likely_cause="The validation failed with an unexpected error, see the logs.",
        )

    def _exchange_rate(
        self, expected: ExpectedBilling, platform: OrganizationSppSummaryRow
    ) -> Decimal:
        if expected.invoices is not None and expected.invoices.lines:
            return expected.invoices.exchange_rate
        return platform.exchange_rate if platform.exchange_rate > 0 else Decimal(1)
