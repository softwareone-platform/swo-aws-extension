"""Models for the AWS billing validation."""

from dataclasses import dataclass, field
from decimal import Decimal

from swo_aws_extension.constants import DEC_ZERO, SupportTypesEnum

HUNDRED = Decimal(100)


@dataclass(frozen=True)
class AgreementDiscounts:
    """Discount related parameters read from a platform agreement."""

    agreement_id: str
    mpa: str
    authorization_id: str = ""
    handshake_approved: bool = False
    support_type: str | None = None
    service_discount: Decimal = DEC_ZERO
    service_discount_type: str | None = None
    support_discount: Decimal = DEC_ZERO
    pls_discount: Decimal = DEC_ZERO

    @property
    def is_pls(self) -> bool:
        """Whether the agreement is configured with Partner Led Support."""
        return self.support_type == SupportTypesEnum.PARTNER_LED_SUPPORT

    @property
    def is_resold_support(self) -> bool:
        """Whether the agreement is configured with AWS resold support."""
        return self.support_type == SupportTypesEnum.AWS_RESOLD_SUPPORT


@dataclass
class InvoiceLine:
    """One AWS invoice mapped to the manual validation sheet columns."""

    invoice_id: str
    invoicing_entity: str
    billing_entity: str
    invoice_type: str
    charges: Decimal
    spp_discount: Decimal
    other_adjustments: Decimal
    cost: Decimal
    tax: Decimal
    currency: str
    exchange_rate: Decimal
    base_currency: str
    has_spp_breakdown: bool = False

    @property
    def is_marketplace(self) -> bool:
        """Whether the invoice is billed by AWS Marketplace."""
        return self.billing_entity == "AWS_MARKETPLACE"

    @property
    def category(self) -> str:
        """Human readable category used in the manual sheet."""
        return "AWS Marketplace" if self.is_marketplace else "Usage"


@dataclass
class MpaInvoices:
    """All AWS invoices of one MPA account for a billing period."""

    mpa: str
    currency: str
    lines: list[InvoiceLine] = field(default_factory=list)

    @property
    def cost_price(self) -> Decimal:
        """Total before tax paid to AWS (cost price in the manual sheet)."""
        return sum((line.cost for line in self.lines), DEC_ZERO)

    @property
    def list_price(self) -> Decimal:
        """Sum of invoice subtotals (charges in the manual sheet)."""
        return sum((line.charges for line in self.lines), DEC_ZERO)

    @property
    def spp_discount(self) -> Decimal:
        """Total AWS SPP discount, always zero or negative."""
        return sum((line.spp_discount for line in self.lines), DEC_ZERO)

    @property
    def principal_total(self) -> Decimal:
        """Total (taxes included) of the principal invoice, as the billing journal picks it.

        The principal invoice is the one carrying the AWS SPP discount breakdown, or the
        first invoice billed by AWS itself when none does. When its total is zero the
        usage was fully covered by credits and the journal returns the SPP discount to
        the customer instead of keeping it, whatever other invoices (one-time purchases,
        marketplace) the MPA has.
        """
        principal = next((line for line in self.lines if line.has_spp_breakdown), None)
        if principal is None:
            principal = next((line for line in self.lines if not line.is_marketplace), None)
        if principal is None:
            return DEC_ZERO
        return principal.cost + principal.tax

    @property
    def exchange_rate(self) -> Decimal:
        """Highest exchange rate found in the invoices, 1 when none applies."""
        rates = [line.exchange_rate for line in self.lines if line.exchange_rate > DEC_ZERO]
        return max(rates) if rates else Decimal(1)


@dataclass
class ServiceSplit:
    """Support and usage amounts that cannot be derived from the invoice summaries.

    The AWS invoice summary only carries totals, so the split between usage and
    support (needed for support discounts and PLS) comes from the per-service
    rows of the platform billing report. Amounts are in the agreement currency.
    """

    enterprise_support_charge: Decimal = DEC_ZERO
    enterprise_support_spp: Decimal = DEC_ZERO
    resold_support_charge: Decimal = DEC_ZERO
    resold_support_spp: Decimal = DEC_ZERO
    usage_base: Decimal = DEC_ZERO

    @property
    def support_spp(self) -> Decimal:
        """SPP discount on every support service."""
        return self.enterprise_support_spp + self.resold_support_spp

    @property
    def has_enterprise_support(self) -> bool:
        """Whether AWS Enterprise Support was charged."""
        return self.enterprise_support_charge != DEC_ZERO
