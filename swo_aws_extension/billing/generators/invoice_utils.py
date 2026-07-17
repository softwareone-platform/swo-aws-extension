from decimal import Decimal

SPP_DISCOUNT_DESCRIPTION = "Discount (AWS SPP Discount)"
MAX_INVOICE_ID_LENGTH = 20
_INVOICE_ID_SUFFIX_LENGTH = 4
_OVERFLOW_MARKER = ".."
_SUFFIX_PREFIX = "-"
_SEPARATOR = ","


def merge_invoice_ids(existing_id: str, new_id: str) -> str:
    """Merge invoice IDs keeping only the unique suffix (last 4 chars) of each.

    Each suffix is prefixed with ``-`` to signal truncation.
    The result must fit within MAX_INVOICE_ID_LENGTH characters.
    When it overflows, an ellipsis marker replaces the newest suffix.
    """
    if not new_id:
        return existing_id
    new_suffix = _SUFFIX_PREFIX + new_id[-_INVOICE_ID_SUFFIX_LENGTH:]
    if _SEPARATOR not in existing_id:
        existing_id = _SUFFIX_PREFIX + existing_id[-_INVOICE_ID_SUFFIX_LENGTH:]
    candidate = _SEPARATOR.join((existing_id, new_suffix))
    if len(candidate) <= MAX_INVOICE_ID_LENGTH:
        return candidate
    truncated = _SEPARATOR.join((existing_id, _OVERFLOW_MARKER))
    if len(truncated) <= MAX_INVOICE_ID_LENGTH:
        return truncated
    return existing_id


def belongs_to_mpa(invoice: dict, mpa_account: str) -> bool:
    """Check whether the invoice belongs to the given MPA account."""
    bill_source_accounts = invoice.get("BillSourceAccounts")
    if bill_source_accounts is not None:
        return mpa_account in bill_source_accounts
    return invoice.get("AccountId") == mpa_account


def is_primary_invoice(invoice: dict) -> bool:
    """Check whether the invoice contains an AWS SPP discount breakdown."""
    breakdowns = (
        invoice
        .get("BaseCurrencyAmount", {})
        .get("AmountBreakdown", {})
        .get("Discounts", {})
        .get("Breakdown", [])
    )
    return any(breakdown.get("Description") == SPP_DISCOUNT_DESCRIPTION for breakdown in breakdowns)


def get_invoice_rate(invoice: dict) -> Decimal:
    """Extract the payment-currency exchange rate from a raw invoice."""
    return Decimal(
        invoice.get("PaymentCurrencyAmount", {}).get("CurrencyExchangeDetails", {}).get("Rate", 0)
    )


def invoice_amount(invoice: dict, currency_key: str, amount_key: str) -> Decimal:
    """Read a Decimal amount from a nested currency section of a raw invoice."""
    return Decimal(invoice.get(currency_key, {}).get(amount_key, 0))
