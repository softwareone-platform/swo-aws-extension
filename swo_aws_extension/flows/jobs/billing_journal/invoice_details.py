from decimal import Decimal


class InvoiceDetails:
    """Class to prepare journal invoice details."""

    def __init__(
        self,
        item_external_id,
        service_name,
        amount,
        account_id,
        account_invoices,
        invoice_entity,
        partner_discount,
    ):
        self.service_name = service_name
        self.account_id = account_id
        self.invoice_entity = invoice_entity
        aws_invoice_details = account_invoices.get("invoice_entities", {}).get(invoice_entity, {})
        self.invoice_id = aws_invoice_details.get("invoice_id")
        self.amount = self._calculate_service_amount(aws_invoice_details, amount)
        self.error = self._get_invoice_error_msg(
            item_external_id, aws_invoice_details, partner_discount
        )

    def _calculate_service_amount(self, aws_invoice_details, amount):
        """Calculate the service amount based on currency exchange rate."""
        payment_currency = aws_invoice_details.get("payment_currency_code", "")
        base_currency = aws_invoice_details.get("base_currency_code", "")
        if payment_currency != base_currency:
            exchange_rate = aws_invoice_details.get("exchange_rate", Decimal(0))
            return round(amount * exchange_rate, 6)
        return amount

    def _get_invoice_error_msg(self, item_external_id, aws_invoice_details, partner_discount):
        if item_external_id:
            return None

        payment_currency = aws_invoice_details.get("payment_currency_code", "")
        partner_amount = self.amount - abs(partner_discount)
        net_amount = self.amount - partner_amount

        discount = 0 if self.amount == 0 else net_amount / self.amount * 100

        return (
            f"{self.account_id} - Service {self.service_name} with amount {self.amount} "
            f"{payment_currency} and discount {discount} did not match any "
            f"subscription item."
        )
