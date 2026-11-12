"""Map AWS ``list_invoice_summaries`` results to the manual validation sheet."""

from dataclasses import dataclass
from decimal import Decimal

from swo_aws_extension.billing.models.invoice import OrganizationInvoice, RawInvoice
from swo_aws_extension.billing.validation.models import InvoiceLine, MpaInvoices
from swo_aws_extension.constants import DEC_ZERO

BASE_CURRENCY_KEY = "BaseCurrencyAmount"
PAYMENT_CURRENCY_KEY = "PaymentCurrencyAmount"


@dataclass(frozen=True)
class _Amounts:
    """Amounts of one currency section of an invoice."""

    charges: Decimal
    spp_discount: Decimal
    cost: Decimal
    total: Decimal


class InvoiceMapper:
    """Build the per-MPA invoice view used by the validation.

    Amounts are expressed in the authorization currency following the same
    rule as the billing journal: the payment currency section of the invoice
    is used when it is reported in that currency, otherwise the base (USD)
    amounts are converted with the exchange rate the journal resolved for the
    invoice entity, or with the one found in sibling invoices when the journal
    entities are not given.
    """

    def __init__(
        self,
        invoice_summaries: list[dict],
        currency: str,
        organization_invoice: OrganizationInvoice | None = None,
    ) -> None:
        self._invoices = [RawInvoice(summary) for summary in invoice_summaries]
        self._currency = currency
        self._entities = organization_invoice.entities if organization_invoice else {}

    def for_mpa(self, mpa: str) -> MpaInvoices:
        """Return the invoices that belong to the given MPA account."""
        invoices = [invoice for invoice in self._invoices if invoice.belongs_to_mpa(mpa)]
        fallback_rate = max(
            (
                invoice.exchange_rate
                for invoice in invoices
                if invoice.has_payment_rate(self._currency)
            ),
            default=DEC_ZERO,
        )
        lines = [self._build_line(invoice, fallback_rate) for invoice in invoices]
        return MpaInvoices(mpa=mpa, currency=self._currency, lines=lines)

    def _build_line(self, invoice: RawInvoice, fallback_rate: Decimal) -> InvoiceLine:
        """Read the invoice amounts in the authorization currency.

        The payment currency section is used when the invoice reports it in that
        currency, otherwise the base (USD) amounts are converted with the rate of
        the journal entity, falling back to the rate found in sibling invoices.
        """
        own_rate = invoice.has_payment_rate(self._currency)
        if own_rate:
            amounts = _read_amounts(invoice, PAYMENT_CURRENCY_KEY, Decimal(1))
            rate = invoice.exchange_rate
        else:
            rate = self._entity_rate(invoice) or fallback_rate
            rate = rate if rate > DEC_ZERO else Decimal(1)
            amounts = _read_amounts(invoice, BASE_CURRENCY_KEY, rate)
        return InvoiceLine(
            invoice_id=invoice.invoice_id,
            invoicing_entity=invoice.invoicing_entity,
            billing_entity=invoice.billing_entity,
            invoice_type=invoice.invoice_type,
            charges=amounts.charges,
            spp_discount=amounts.spp_discount,
            other_adjustments=amounts.cost - amounts.charges - amounts.spp_discount,
            cost=amounts.cost,
            tax=amounts.total - amounts.cost,
            currency=self._currency,
            exchange_rate=rate,
            base_currency=invoice.base_currency_code or "USD",
            has_spp_breakdown=invoice.is_primary,
            own_exchange_rate=own_rate,
        )

    def _entity_rate(self, invoice: RawInvoice) -> Decimal:
        """Rate the journal applies to the entity of the invoice, zero when unknown."""
        entity = self._entities.get(invoice.entity_key)
        return entity.exchange_rate if entity else DEC_ZERO


def _read_amounts(invoice: RawInvoice, currency_key: str, multiplier: Decimal) -> _Amounts:
    """Read one currency section of the invoice, scaled to the authorization currency."""
    return _Amounts(
        charges=invoice.breakdown_amount(currency_key, "SubTotalAmount") * multiplier,
        spp_discount=invoice.spp_discount(currency_key) * multiplier,
        cost=invoice.amount(currency_key, "TotalAmountBeforeTax") * multiplier,
        total=invoice.amount(currency_key, "TotalAmount") * multiplier,
    )
