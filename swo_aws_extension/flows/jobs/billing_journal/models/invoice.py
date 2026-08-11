"""Invoice models for billing journal."""

from dataclasses import dataclass, field
from decimal import Decimal

SPP_DISCOUNT_DESCRIPTION = "Discount (AWS SPP Discount)"


@dataclass
class RawInvoice:  # noqa: WPS214
    """Typed accessors over a raw AWS invoice summary."""

    summary: dict

    @property
    def invoice_id(self) -> str:
        """The AWS invoice ID."""
        return self.summary.get("InvoiceId", "")

    @property
    def invoicing_entity(self) -> str:
        """The AWS invoicing entity name."""
        return self.summary.get("Entity", {}).get("InvoicingEntity", "")

    @property
    def billing_entity(self) -> str:
        """The billing entity name, AWS by default."""
        return self.summary.get("Entity", {}).get("BillingEntity", "AWS")

    @property
    def entity_key(self) -> str:
        """Key that groups invoices by invoicing and billing entity."""
        return f"{self.invoicing_entity}:{self.billing_entity}"

    @property
    def base_currency_code(self) -> str:
        """The base currency code."""
        return self.summary.get("BaseCurrencyAmount", {}).get("CurrencyCode", "")

    @property
    def payment_currency_code(self) -> str:
        """The payment currency code."""
        return self.summary.get("PaymentCurrencyAmount", {}).get("CurrencyCode", "")

    @property
    def exchange_rate(self) -> Decimal:
        """The payment-currency exchange rate, zero when missing."""
        return Decimal(
            self.summary
            .get("PaymentCurrencyAmount", {})
            .get("CurrencyExchangeDetails", {})
            .get("Rate", 0)
        )

    @property
    def is_primary(self) -> bool:
        """Whether the invoice contains an AWS SPP discount breakdown."""
        breakdowns = (
            self.summary
            .get("BaseCurrencyAmount", {})
            .get("AmountBreakdown", {})
            .get("Discounts", {})
            .get("Breakdown", [])
        )
        return any(
            breakdown.get("Description") == SPP_DISCOUNT_DESCRIPTION for breakdown in breakdowns
        )

    def belongs_to_mpa(self, mpa_account: str) -> bool:
        """Whether the invoice belongs to the given MPA account."""
        bill_source_accounts = self.summary.get("BillSourceAccounts")
        if bill_source_accounts is not None:
            return mpa_account in bill_source_accounts
        return self.summary.get("AccountId") == mpa_account

    def has_payment_rate(self, currency: str) -> bool:
        """Whether the invoice reports the given payment currency with a positive rate."""
        return self.payment_currency_code == currency and self.exchange_rate > 0

    def amount(self, currency_key: str, amount_key: str) -> Decimal:
        """Read a Decimal amount from a currency section of the invoice."""
        return Decimal(self.summary.get(currency_key, {}).get(amount_key, 0))

    def breakdown_amount(self, currency_key: str, amount_key: str) -> Decimal:
        """Read a Decimal amount from the breakdown of a currency section."""
        return Decimal(
            self.summary.get(currency_key, {}).get("AmountBreakdown", {}).get(amount_key, 0)
        )


@dataclass
class InvoiceEntity:
    """Invoice entity details for a single invoicing entity."""

    invoice_id: str = ""
    base_currency_code: str = ""
    payment_currency_code: str = ""
    exchange_rate: Decimal = field(default_factory=lambda: Decimal(0))
    billing_entity: str = "AWS"
    primary: bool = field(default=False)


@dataclass
class OrganizationInvoice:
    """Processed invoice metrics for an organization."""

    entities: dict[str, InvoiceEntity] = field(default_factory=dict)
    base_total_amount: Decimal = field(default_factory=lambda: Decimal(0))
    base_total_amount_before_tax: Decimal = field(default_factory=lambda: Decimal(0))
    payment_currency_total_amount: Decimal = field(default_factory=lambda: Decimal(0))
    payment_currency_total_amount_before_tax: Decimal = field(default_factory=lambda: Decimal(0))
    payment_currency_subtotal_amount: Decimal = field(default_factory=lambda: Decimal(0))
    principal_invoice_amount: Decimal | None = None

    @property
    def primary_entity_name(self) -> str:
        """Return the name of the entity marked as primary, or empty string."""
        for name, entity in self.entities.items():
            if entity.primary:
                return name
        return ""

    @property
    def primary_invoice_id(self) -> str:
        """Return the invoice ID of the entity marked as primary."""
        for entity in self.entities.values():
            if entity.primary:
                return entity.invoice_id
        return "invoice_id"


@dataclass
class OrganizationInvoiceResult:
    """Global container returned by the generator, includes raw and processed data."""

    raw_data: list[dict] = field(default_factory=list)
    invoice: OrganizationInvoice = field(default_factory=OrganizationInvoice)

    @property
    def invoice_ids(self) -> set[str]:
        """The complete AWS invoice IDs present in the raw invoice summaries."""
        return {summary["InvoiceId"] for summary in self.raw_data if summary.get("InvoiceId")}
