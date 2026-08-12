from decimal import Decimal

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.billing.generators.currency import resolve_service_amount
from swo_aws_extension.billing.generators.invoice_utils import merge_invoice_ids
from swo_aws_extension.billing.models.invoice import (
    InvoiceEntity,
    OrganizationInvoice,
    OrganizationInvoiceResult,
    RawInvoice,
)
from swo_aws_extension.constants import DEC_ZERO
from swo_aws_extension.logger import get_logger
from swo_aws_extension.models import BillingPeriod

logger = get_logger(__name__)


class ExchangeRateResolver:
    """Resolves exchange rates and payment currencies from invoices."""

    def __init__(self, invoices: list[RawInvoice]) -> None:
        self._invoices = invoices

    def get_rate(self, entity_name: str, currency: str) -> Decimal:
        """Get the exchange rate for the given entity and currency."""
        entity_rates = self._extract_rates(currency, entity_name)
        if entity_rates:
            return max(entity_rates)
        return max(self._extract_rates(currency), default=DEC_ZERO)

    def get_payment_currency(self, exchange_rate: Decimal, currency: str) -> str:
        """Get the payment currency code for the given resolved exchange rate and currency."""
        if exchange_rate > DEC_ZERO:
            return currency
        for invoice in self._invoices:
            if invoice.exchange_rate == exchange_rate:
                return invoice.payment_currency_code or "USD"
        return "USD"

    def _extract_rates(self, currency: str, entity_name: str | None = None) -> list[Decimal]:
        return [
            invoice.exchange_rate
            for invoice in self._invoices
            if invoice.has_payment_rate(currency)
            and (not entity_name or invoice.invoicing_entity == entity_name)
        ]


class OrganizationInvoiceBuilder:
    """Builds an OrganizationInvoice from a list of raw invoices."""

    def __init__(self, invoices: list[RawInvoice], currency: str) -> None:
        self._invoices = invoices
        self._currency = currency
        self._resolver = ExchangeRateResolver(invoices)

    def build(self) -> OrganizationInvoice:
        """Aggregate the raw invoices into a single OrganizationInvoice."""
        entities = self._build_entities()
        return OrganizationInvoice(
            entities=entities,
            base_total_amount=self._sum_amounts("BaseCurrencyAmount", "TotalAmount"),
            base_total_amount_before_tax=self._sum_amounts(
                "BaseCurrencyAmount", "TotalAmountBeforeTax"
            ),
            payment_currency_total_amount=self._sum_payment_amounts(entities, "TotalAmount"),
            payment_currency_total_amount_before_tax=self._sum_payment_amounts(
                entities, "TotalAmountBeforeTax"
            ),
            payment_currency_subtotal_amount=self._sum_payment_amounts(
                entities, "SubTotalAmount", breakdown=True
            ),
            principal_invoice_amount=next(
                (
                    invoice.amount("BaseCurrencyAmount", "TotalAmount")
                    for invoice in self._invoices
                    if invoice.is_primary
                ),
                None,
            ),
        )

    def _build_entities(self) -> dict[str, InvoiceEntity]:
        entities: dict[str, InvoiceEntity] = {}
        for invoice in self._invoices:
            entities[invoice.entity_key] = self._build_invoice_entity(
                invoice, entities.get(invoice.entity_key)
            )
        return entities

    def _build_invoice_entity(
        self,
        invoice: RawInvoice,
        existing: InvoiceEntity | None,
    ) -> InvoiceEntity:
        if existing:
            merged_id = merge_invoice_ids(existing.invoice_id, invoice.invoice_id)
            return InvoiceEntity(
                invoice_id=merged_id,
                base_currency_code=existing.base_currency_code,
                payment_currency_code=existing.payment_currency_code,
                exchange_rate=existing.exchange_rate,
                billing_entity=invoice.billing_entity,
                primary=invoice.is_primary or existing.primary,
            )
        exchange_rate = self._resolver.get_rate(invoice.invoicing_entity, self._currency)
        return InvoiceEntity(
            invoice_id=invoice.invoice_id,
            base_currency_code=invoice.base_currency_code,
            payment_currency_code=self._resolver.get_payment_currency(
                exchange_rate, self._currency
            ),
            exchange_rate=exchange_rate,
            billing_entity=invoice.billing_entity,
            primary=invoice.is_primary,
        )

    def _sum_amounts(self, currency_key: str, amount_key: str) -> Decimal:
        return sum(
            (invoice.amount(currency_key, amount_key) for invoice in self._invoices),
            DEC_ZERO,
        )

    def _sum_payment_amounts(
        self,
        entities: dict[str, InvoiceEntity],
        amount_key: str,
        *,
        breakdown: bool = False,
    ) -> Decimal:
        return sum(
            (
                self._payment_amount(invoice, entities, amount_key, breakdown=breakdown)
                for invoice in self._invoices
            ),
            DEC_ZERO,
        )

    def _payment_amount(
        self,
        invoice: RawInvoice,
        entities: dict[str, InvoiceEntity],
        amount_key: str,
        *,
        breakdown: bool = False,
    ) -> Decimal:
        """Payment-currency amount, converting from base with the resolved rate if missing."""
        has_rate = invoice.has_payment_rate(self._currency)
        currency_key = "PaymentCurrencyAmount" if has_rate else "BaseCurrencyAmount"
        if breakdown:
            amount = invoice.breakdown_amount(currency_key, amount_key)
        else:
            amount = invoice.amount(currency_key, amount_key)
        if has_rate:
            return amount
        return resolve_service_amount(amount, entities.get(invoice.entity_key))


class InvoiceGenerator:
    """Fetches and processes invoice data from AWS."""

    def __init__(self, aws_client: AWSClient) -> None:
        self._aws_client = aws_client

    def run(
        self,
        pma_account: str,
        mpa_account: str,
        billing_period: BillingPeriod,
        authorization_currency: str,
    ) -> OrganizationInvoiceResult:
        """Fetch and process invoices for the given account and billing period.

        Args:
            pma_account: The PMA account ID used to call the AWS API.
            mpa_account: The MPA account ID used to filter invoices from the map.
            billing_period: The billing period to fetch invoices for.
            authorization_currency: The currency for the authorization.

        Returns:
            OrganizationInvoiceResult containing raw data and processed invoice.
        """
        invoice_summaries = self._aws_client.list_invoice_summaries_by_account_id(
            pma_account, billing_period.year, billing_period.month
        )
        raw_invoices = [
            invoice
            for invoice in map(RawInvoice, invoice_summaries)
            if invoice.belongs_to_mpa(mpa_account)
        ]
        invoice = OrganizationInvoiceBuilder(raw_invoices, authorization_currency).build()

        for entity_name, entity in invoice.entities.items():
            logger.info(
                "Invoice entity: %s | invoice_id=%s | base=%s | payment=%s | exchange_rate=%s",
                entity_name,
                entity.invoice_id,
                entity.base_currency_code,
                entity.payment_currency_code,
                entity.exchange_rate,
            )

        return OrganizationInvoiceResult(
            raw_data=[raw_invoice.summary for raw_invoice in raw_invoices],
            invoice=invoice,
        )
