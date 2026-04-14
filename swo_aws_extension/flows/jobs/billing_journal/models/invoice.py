"""Invoice models for billing journal."""

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class InvoiceEntity:
    """Invoice entity details for a single invoicing entity."""

    invoice_id: str = ""
    base_currency_code: str = ""
    payment_currency_code: str = ""
    exchange_rate: Decimal = field(default_factory=lambda: Decimal(0))
    primary: bool = field(default=False)


@dataclass
class OrganizationInvoice:
    """Processed invoice metrics for an organization."""

    entities: dict[str, InvoiceEntity] = field(default_factory=dict)
    base_total_amount: Decimal = field(default_factory=lambda: Decimal(0))
    base_total_amount_before_tax: Decimal = field(default_factory=lambda: Decimal(0))
    payment_currency_total_amount: Decimal = field(default_factory=lambda: Decimal(0))
    payment_currency_total_amount_before_tax: Decimal = field(default_factory=lambda: Decimal(0))
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
