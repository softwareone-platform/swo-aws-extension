from decimal import Decimal

from swo_aws_extension.constants import DEC_ZERO
from swo_aws_extension.flows.jobs.billing_journal.models.invoice import InvoiceEntity


def resolve_service_amount(
    amount: Decimal,
    invoice_entity: InvoiceEntity | None,
) -> Decimal:
    """Calculate the service amount converted to the local payment currency."""
    if not invoice_entity:
        return amount

    if invoice_entity.payment_currency_code == invoice_entity.base_currency_code:
        return amount
    if invoice_entity.exchange_rate <= DEC_ZERO:
        return amount

    return round(amount * invoice_entity.exchange_rate, 6)
