"""Compare the expected billing against the platform results."""

from decimal import Decimal

from swo_aws_extension.billing.models.journal_result import (
    OrganizationSppSummaryRow,
)
from swo_aws_extension.billing.validation.results import (
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

    The tolerance is expressed in USD and converted to the agreement currency with the
    exchange rate of the invoices, so 0.05 USD becomes roughly 800 IDR or 0.04 EUR.
    """

    def __init__(self, tolerance: Decimal = DEFAULT_TOLERANCE) -> None:
        self._tolerance = tolerance

    def validate(
        self,
        expected: ExpectedBilling,
        platform: OrganizationSppSummaryRow | None,
    ) -> AgreementValidation:
        """Compare cost, list price, SPP discount and sales price within the tolerance."""
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
        )
        if platform is None:
            validation.status = ValidationStatus.MISSING_IN_PLATFORM
            validation.notes.append("No SPP Summary row was produced for the agreement.")
            return validation

        tolerance = self._tolerance * self._exchange_rate(expected, platform)
        validation.checks = [
            CheckResult(COST_PRICE_CHECK, expected.cost_price, platform.pp, tolerance),
            CheckResult("List price", expected.list_price, platform.list_price, tolerance),
            CheckResult("SPP discount", expected.spp_discount, platform.spp_discount, tolerance),
            CheckResult(SALES_PRICE_CHECK, expected.sales_price, platform.sp, tolerance),
            CheckResult(
                "SP from markup (PP * (1 + markup))",
                platform.pp * (1 + platform.markup),
                platform.sp,
                tolerance,
            ),
        ]
        if validation.failed_checks:
            validation.status = ValidationStatus.MISMATCH
            self._explain(validation)
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
            notes=["No AWS invoices found for the MPA account."],
        )

    def _explain(self, validation: AgreementValidation) -> None:
        failed = {check.name for check in validation.failed_checks}
        if failed == {SALES_PRICE_CHECK}:
            validation.notes.append(
                "Invoice totals match but the journal total does not: the journal is built "
                "from Cost Explorer usage, check credits, refunds, unbilled record types or "
                "the agreement discounts."
            )
        elif COST_PRICE_CHECK in failed:
            validation.notes.append(
                "The platform cost price does not match the AWS invoices for the MPA."
            )

    def _exchange_rate(
        self, expected: ExpectedBilling, platform: OrganizationSppSummaryRow
    ) -> Decimal:
        if expected.invoices is not None and expected.invoices.lines:
            return expected.invoices.exchange_rate
        return platform.exchange_rate if platform.exchange_rate > 0 else Decimal(1)
