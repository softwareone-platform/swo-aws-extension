"""Map AWS ``list_invoice_summaries`` results to the manual validation sheet."""

from decimal import Decimal

from swo_aws_extension.billing.validation.models import InvoiceLine, MpaInvoices
from swo_aws_extension.constants import DEC_ZERO

SPP_DISCOUNT_DESCRIPTION = "Discount (AWS SPP Discount)"
BASE_CURRENCY_KEY = "BaseCurrencyAmount"
PAYMENT_CURRENCY_KEY = "PaymentCurrencyAmount"


def _decimal(raw_value) -> Decimal:
    return Decimal(str(raw_value or 0))


def _belongs_to_mpa(summary: dict, mpa: str) -> bool:
    bill_source_accounts = summary.get("BillSourceAccounts")
    if bill_source_accounts is not None:
        return mpa in bill_source_accounts
    return summary.get("AccountId") == mpa


def _payment_rate(summary: dict, currency: str) -> Decimal:
    payment = summary.get(PAYMENT_CURRENCY_KEY, {})
    if payment.get("CurrencyCode") != currency:
        return DEC_ZERO
    return _decimal(payment.get("CurrencyExchangeDetails", {}).get("Rate"))


def _spp_discount(amounts: dict) -> Decimal:
    discounts = amounts.get("AmountBreakdown", {}).get("Discounts", {})
    breakdown = discounts.get("Breakdown", [])
    spp = sum(
        (
            _decimal(entry.get("Amount"))
            for entry in breakdown
            if entry.get("Description") == SPP_DISCOUNT_DESCRIPTION
        ),
        DEC_ZERO,
    )
    return -abs(spp)


class InvoiceMapper:
    """Build the per-MPA invoice view used by the validation.

    Amounts are expressed in the authorization currency following the same
    rule as the billing journal: the payment currency section of the invoice
    is used when it is reported in that currency, otherwise the base (USD)
    amounts are converted with the exchange rate found in sibling invoices.
    """

    def __init__(self, invoice_summaries: list[dict], currency: str) -> None:
        self._summaries = invoice_summaries
        self._currency = currency

    def for_mpa(self, mpa: str) -> MpaInvoices:
        """Return the invoices that belong to the given MPA account."""
        summaries = [summary for summary in self._summaries if _belongs_to_mpa(summary, mpa)]
        fallback_rate = self._fallback_rate(summaries)
        lines = [self._build_line(summary, fallback_rate) for summary in summaries]
        return MpaInvoices(mpa=mpa, currency=self._currency, lines=lines)

    def _fallback_rate(self, summaries: list[dict]) -> Decimal:
        rates = [_payment_rate(summary, self._currency) for summary in summaries]
        return max((rate for rate in rates if rate > DEC_ZERO), default=DEC_ZERO)

    def _build_line(self, summary: dict, fallback_rate: Decimal) -> InvoiceLine:
        figures = self._figures(summary, fallback_rate)
        return InvoiceLine(
            invoice_id=summary.get("InvoiceId", ""),
            invoicing_entity=summary.get("Entity", {}).get("InvoicingEntity", ""),
            billing_entity=summary.get("Entity", {}).get("BillingEntity", "AWS"),
            invoice_type=summary.get("InvoiceType", "INVOICE"),
            charges=figures["charges"],
            spp_discount=figures["spp"],
            other_adjustments=figures["cost"] - figures["charges"] - figures["spp"],
            cost=figures["cost"],
            tax=figures["total"] - figures["cost"],
            currency=self._currency,
            exchange_rate=figures["rate"],
            base_currency=summary.get(BASE_CURRENCY_KEY, {}).get("CurrencyCode", "USD"),
        )

    def _figures(self, summary: dict, fallback_rate: Decimal) -> dict[str, Decimal]:
        """Read the invoice amounts in the authorization currency.

        The payment currency section is used when the invoice reports it in that
        currency, otherwise the base (USD) amounts are converted with the fallback
        exchange rate found in sibling invoices.
        """
        rate = _payment_rate(summary, self._currency)
        if rate > DEC_ZERO:
            amounts = summary.get(PAYMENT_CURRENCY_KEY, {})
            multiplier = Decimal(1)
        else:
            amounts = summary.get(BASE_CURRENCY_KEY, {})
            rate = fallback_rate if fallback_rate > DEC_ZERO else Decimal(1)
            multiplier = rate
        return {
            "rate": rate,
            "charges": _decimal(amounts.get("AmountBreakdown", {}).get("SubTotalAmount"))
            * multiplier,
            "spp": _spp_discount(amounts) * multiplier,
            "cost": _decimal(amounts.get("TotalAmountBeforeTax")) * multiplier,
            "total": _decimal(amounts.get("TotalAmount")) * multiplier,
        }
