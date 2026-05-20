from decimal import Decimal

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.constants import DEC_ZERO
from swo_aws_extension.flows.jobs.billing_journal.models.billing_period import BillingPeriod
from swo_aws_extension.flows.jobs.billing_journal.models.invoice import (
    InvoiceEntity,
    OrganizationInvoice,
    OrganizationInvoiceResult,
)
from swo_aws_extension.logger import get_logger

logger = get_logger(__name__)
SPP_DISCOUNT_DESCRIPTION = "Discount (AWS SPP Discount)"


class ExchangeRateResolver:
    """Resolves exchange rates and payment currencies from invoices."""

    def __init__(self, raw_invoices: list[dict]) -> None:
        self._raw_invoices = raw_invoices

    def get_rate(self, entity_name: str, currency: str) -> Decimal:
        """Get the exchange rate for the given entity and currency."""
        entity_rates = self._extract_rates(currency, entity_name)
        if entity_rates:
            return max(entity_rates)
        return max(self._extract_rates(currency), default=DEC_ZERO)

    def get_payment_currency(self, exchange_rate: Decimal) -> str:
        """Get the payment currency code for the given exchange rate."""
        for inv in self._raw_invoices:
            rate = self._get_invoice_rate(inv)
            if rate == exchange_rate:
                return inv.get("PaymentCurrencyAmount", {}).get("CurrencyCode", "USD")
        return "USD"

    def _extract_rates(self, currency: str, entity_name: str | None = None) -> list[Decimal]:
        rates = []
        for inv in self._raw_invoices:
            if inv.get("PaymentCurrencyAmount", {}).get("CurrencyCode") != currency:
                continue
            if entity_name and inv.get("Entity", {}).get("InvoicingEntity") != entity_name:
                continue
            rates.append(self._get_invoice_rate(inv))
        return rates

    def _get_invoice_rate(self, invoice: dict) -> Decimal:
        return Decimal(
            invoice
            .get("PaymentCurrencyAmount", {})
            .get("CurrencyExchangeDetails", {})
            .get("Rate", 0)
        )


class InvoiceGenerator:
    """Fetches and processes invoice data from AWS."""

    def __init__(self, aws_client: AWSClient) -> None:
        self._aws_client = aws_client

    def run(
        self,
        mpa_account: str,
        billing_period: BillingPeriod,
        authorization_currency: str,
    ) -> OrganizationInvoiceResult:
        """Fetch and process invoices for the given account and billing period.

        Args:
            mpa_account: The MPA account ID.
            billing_period: The billing period to fetch invoices for.
            authorization_currency: The currency for the authorization.

        Returns:
            OrganizationInvoiceResult containing raw data and processed invoice.
        """
        invoice_summaries = self._aws_client.list_invoice_summaries_by_account_id(
            mpa_account, billing_period.year, billing_period.month
        )
        raw_invoices = [inv for inv in invoice_summaries if inv.get("AccountId") == mpa_account]

        invoice = self._build_organization_invoice(raw_invoices, authorization_currency)

        for entity_name, entity in invoice.entities.items():
            logger.info(
                "Invoice entity: %s | invoice_id=%s | base=%s | payment=%s | exchange_rate=%s",
                entity_name,
                entity.invoice_id,
                entity.base_currency_code,
                entity.payment_currency_code,
                entity.exchange_rate,
            )

        return OrganizationInvoiceResult(raw_data=raw_invoices, invoice=invoice)

    def _build_organization_invoice(
        self, raw_invoices: list[dict], currency: str
    ) -> OrganizationInvoice:
        resolver = ExchangeRateResolver(raw_invoices)
        entities = self._build_entities(raw_invoices, currency, resolver)

        return OrganizationInvoice(
            entities=entities,
            base_total_amount=self._sum_amounts(raw_invoices, "BaseCurrencyAmount", "TotalAmount"),
            base_total_amount_before_tax=self._sum_amounts(
                raw_invoices, "BaseCurrencyAmount", "TotalAmountBeforeTax"
            ),
            payment_currency_total_amount=self._sum_amounts(
                raw_invoices, "PaymentCurrencyAmount", "TotalAmount"
            ),
            payment_currency_total_amount_before_tax=self._sum_amounts(
                raw_invoices, "PaymentCurrencyAmount", "TotalAmountBeforeTax"
            ),
            principal_invoice_amount=self._get_principal_amount(raw_invoices),
        )

    def _build_entities(
        self, raw_invoices: list[dict], currency: str, resolver: ExchangeRateResolver
    ) -> dict[str, InvoiceEntity]:
        entities: dict[str, InvoiceEntity] = {}

        for invoice in raw_invoices:
            entity_name = invoice.get("Entity", {}).get("InvoicingEntity")
            existing = entities.get(entity_name)
            if existing:
                entities[entity_name] = InvoiceEntity(
                    invoice_id=f"{existing.invoice_id},{invoice.get('InvoiceId', '')}",
                    base_currency_code=existing.base_currency_code,
                    payment_currency_code=existing.payment_currency_code,
                    exchange_rate=existing.exchange_rate,
                    primary=self._is_primary_invoice(invoice) or existing.primary,
                )
            else:
                entity_name = invoice.get("Entity", {}).get("InvoicingEntity")
                exchange_rate = resolver.get_rate(entity_name, currency)

                entities[entity_name] = InvoiceEntity(
                    invoice_id=invoice.get("InvoiceId", ""),
                    base_currency_code=invoice.get("BaseCurrencyAmount", {}).get(
                        "CurrencyCode", ""
                    ),
                    payment_currency_code=resolver.get_payment_currency(exchange_rate),
                    exchange_rate=exchange_rate,
                    primary=self._is_primary_invoice(invoice),
                )

        return entities

    def _get_principal_amount(self, raw_invoices: list[dict]) -> Decimal | None:
        for invoice in raw_invoices:
            if self._is_primary_invoice(invoice):
                return Decimal(invoice.get("BaseCurrencyAmount", {}).get("TotalAmount", 0))
        return None

    def _sum_amounts(self, invoices: list[dict], currency_key: str, amount_key: str) -> Decimal:
        return sum(
            (Decimal(inv.get(currency_key, {}).get(amount_key, 0)) for inv in invoices),
            DEC_ZERO,
        )

    def _is_primary_invoice(self, invoice: dict) -> bool:
        breakdowns = (
            invoice
            .get("BaseCurrencyAmount", {})
            .get("AmountBreakdown", {})
            .get("Discounts", {})
            .get("Breakdown", [])
        )
        return any(
            breakdown.get("Description") == SPP_DISCOUNT_DESCRIPTION for breakdown in breakdowns
        )
