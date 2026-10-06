"""Compute the expected sales and cost prices following the manual validation sheet.

The manual sheet works per usage account (agreement / MPA):

* ``Cost price total`` = charges + SPP discount (+ support + marketplace), that is the
  AWS invoice total before tax.
* ``Sales Price total`` = charges (+ support + marketplace) - discount * SPP discount,
  where only the share of the SPP discount configured in the agreement is passed to
  the customer and the rest is kept by SWO.
* For Partner Led Support the AWS Enterprise Support charge is removed and replaced
  by the SWO support charge (a percentage of the usage).
"""

from decimal import Decimal

from swo_aws_extension.billing.validation.models import (
    HUNDRED,
    AgreementDiscounts,
    MpaInvoices,
    ServiceSplit,
)
from swo_aws_extension.billing.validation.results import ExpectedBilling
from swo_aws_extension.constants import DEC_ZERO, ServiceDiscountTypeEnum


class ExpectedBillingCalculator:
    """Apply the manual validation operations to the AWS invoices of an agreement."""

    def __init__(self, pls_charge_percentage: Decimal) -> None:
        self._pls_charge_percentage = pls_charge_percentage

    def calculate(
        self,
        expected: ExpectedBilling,
        invoices: MpaInvoices,
        discounts: AgreementDiscounts | None,
        split: ServiceSplit | None,
    ) -> ExpectedBilling:
        """Fill the expected prices of the given agreement.

        Args:
            expected: Agreement identification, filled in place and returned.
            invoices: AWS invoices of the MPA for the billing period.
            discounts: Discount parameters of the agreement, None when not found.
            split: Support/usage split from the billing report, None when unavailable.

        Returns:
            The expected billing with cost, list and sales price and the applied steps.
        """
        expected.invoices = invoices
        expected.discounts = discounts
        expected.split = split
        expected.cost_price = invoices.cost_price
        expected.list_price = invoices.list_price
        expected.spp_discount = invoices.spp_discount

        expected.add_step("AWS cost price (invoice total before tax)", invoices.cost_price)
        if invoices.aws_total == DEC_ZERO:
            expected.notes.append(
                "AWS invoice total is 0 (usage covered by credits): the SPP discount is "
                "returned to the customer and no extra discount applies."
            )
            return expected

        expected.add_step("SPP discount kept by SWO", -invoices.spp_discount)
        if discounts is None:
            expected.notes.append("Agreement not found in the platform: no discounts applied.")
            return expected

        self._apply_service_discount(expected, discounts, split)
        self._apply_support_discount(expected, discounts, split)
        self._apply_pls(expected, discounts, split)
        return expected

    def _apply_service_discount(
        self,
        expected: ExpectedBilling,
        discounts: AgreementDiscounts,
        split: ServiceSplit | None,
    ) -> None:
        if not discounts.handshake_approved or discounts.service_discount <= DEC_ZERO:
            return
        if discounts.service_discount_type == ServiceDiscountTypeEnum.USAGE_AMOUNT:
            base = split.usage_base if split else DEC_ZERO
            label = "usage"
            if split is None:
                expected.notes.append("Usage based discount needs the billing report rows.")
        else:
            support_spp = split.support_spp if split else DEC_ZERO
            base = abs(expected.spp_discount - support_spp)
            label = "SPP discount on usage"
        amount = base * discounts.service_discount / HUNDRED
        expected.add_step(
            f"SWO service discount {discounts.service_discount}% of {label}",
            -amount,
        )

    def _apply_support_discount(
        self,
        expected: ExpectedBilling,
        discounts: AgreementDiscounts,
        split: ServiceSplit | None,
    ) -> None:
        if not discounts.handshake_approved or not discounts.is_resold_support:
            return
        if discounts.support_discount <= DEC_ZERO:
            return
        if split is None:
            expected.notes.append("Support discount needs the billing report rows.")
            return
        amount = abs(split.resold_support_spp) * discounts.support_discount / HUNDRED
        expected.add_step(
            f"SWO support discount {discounts.support_discount}% of SPP discount on support",
            -amount,
        )

    def _apply_pls(
        self,
        expected: ExpectedBilling,
        discounts: AgreementDiscounts,
        split: ServiceSplit | None,
    ) -> None:
        has_enterprise = split is not None and split.has_enterprise_support
        if discounts.is_pls != has_enterprise:
            expected.notes.append(
                "PLS mismatch: parameter={} but report {} AWS Support (Enterprise).".format(
                    "PLS" if discounts.is_pls else "Resold Support",
                    "has" if has_enterprise else "does not have",
                )
            )
        if not discounts.is_pls or split is None or not has_enterprise:
            return

        expected.add_step(
            "AWS Enterprise Support not charged (PLS)",
            -split.enterprise_support_charge,
        )
        expected.add_step(
            f"SWO Enterprise support for AWS {self._pls_charge_percentage}% of usage",
            split.usage_base * self._pls_charge_percentage / HUNDRED,
        )
        if discounts.handshake_approved and discounts.pls_discount > DEC_ZERO:
            expected.add_step(
                f"SWO PLS discount {discounts.pls_discount}% of usage",
                -(split.usage_base * discounts.pls_discount / HUNDRED),
            )
