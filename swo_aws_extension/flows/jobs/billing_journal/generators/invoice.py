from decimal import Decimal

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.constants import DEC_ZERO
from swo_aws_extension.flows.jobs.billing_journal.generators.invoice_utils import (
    belongs_to_mpa,
    get_invoice_rate,
    invoice_amount,
    is_primary_invoice,
    merge_invoice_ids,
)
from swo_aws_extension.flows.jobs.billing_journal.models.billing_period import BillingPeriod
from swo_aws_extension.flows.jobs.billing_journal.models.invoice import (
    InvoiceEntity,
    OrganizationInvoice,
    OrganizationInvoiceResult,
)
from swo_aws_extension.logger import get_logger

logger = get_logger(__name__)


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
            rate = get_invoice_rate(inv)
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
            rates.append(get_invoice_rate(inv))
        return rates


class OrganizationInvoiceBuilder:
    """Builds an OrganizationInvoice from a list of raw invoice dicts."""

    def __init__(self, raw_invoices: list[dict], currency: str) -> None:
        self._raw_invoices = raw_invoices
        self._currency = currency
        self._resolver = ExchangeRateResolver(raw_invoices)

    def build(self) -> OrganizationInvoice:
        """Aggregate the raw invoices into a single OrganizationInvoice."""
        return OrganizationInvoice(
            entities=self._build_entities(),
            base_total_amount=self._sum_amounts("BaseCurrencyAmount", "TotalAmount"),
            base_total_amount_before_tax=self._sum_amounts(
                "BaseCurrencyAmount", "TotalAmountBeforeTax"
            ),
            payment_currency_total_amount=self._sum_amounts("PaymentCurrencyAmount", "TotalAmount"),
            payment_currency_total_amount_before_tax=self._sum_amounts(
                "PaymentCurrencyAmount", "TotalAmountBeforeTax"
            ),
            payment_currency_subtotal_amount=self._sum_breakdown_amounts(
                "PaymentCurrencyAmount", "SubTotalAmount"
            ),
            principal_invoice_amount=self._get_principal_amount(),
        )

    def _build_entities(self) -> dict[str, InvoiceEntity]:
        entities: dict[str, InvoiceEntity] = {}
        for invoice in self._raw_invoices:
            entity = invoice.get("Entity", {})
            entity_key = f"{entity.get('InvoicingEntity', '')}:{entity.get('BillingEntity', 'AWS')}"
            entities[entity_key] = self._build_invoice_entity(
                invoice, entity, entities.get(entity_key)
            )
        return entities

    def _build_invoice_entity(
        self,
        invoice: dict,
        entity: dict,
        existing: InvoiceEntity | None,
    ) -> InvoiceEntity:
        billing_entity = entity.get("BillingEntity", "AWS")
        if existing:
            merged_id = merge_invoice_ids(existing.invoice_id, invoice.get("InvoiceId", ""))
            return InvoiceEntity(
                invoice_id=merged_id,
                base_currency_code=existing.base_currency_code,
                payment_currency_code=existing.payment_currency_code,
                exchange_rate=existing.exchange_rate,
                billing_entity=billing_entity,
                primary=is_primary_invoice(invoice) or existing.primary,
            )
        exchange_rate = self._resolver.get_rate(entity.get("InvoicingEntity", ""), self._currency)
        return InvoiceEntity(
            invoice_id=invoice.get("InvoiceId", ""),
            base_currency_code=invoice.get("BaseCurrencyAmount", {}).get("CurrencyCode", ""),
            payment_currency_code=self._resolver.get_payment_currency(exchange_rate),
            exchange_rate=exchange_rate,
            billing_entity=billing_entity,
            primary=is_primary_invoice(invoice),
        )

    def _sum_amounts(self, currency_key: str, amount_key: str) -> Decimal:
        return sum(
            (invoice_amount(inv, currency_key, amount_key) for inv in self._raw_invoices),
            DEC_ZERO,
        )

    def _sum_breakdown_amounts(self, currency_key: str, amount_key: str) -> Decimal:
        return sum(
            (
                invoice_amount(inv.get(currency_key, {}), "AmountBreakdown", amount_key)
                for inv in self._raw_invoices
            ),
            DEC_ZERO,
        )

    def _get_principal_amount(self) -> Decimal | None:
        for invoice in self._raw_invoices:
            if is_primary_invoice(invoice):
                return Decimal(invoice.get("BaseCurrencyAmount", {}).get("TotalAmount", 0))
        return None


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
        raw_invoices = [inv for inv in invoice_summaries if belongs_to_mpa(inv, mpa_account)]
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

        return OrganizationInvoiceResult(raw_data=raw_invoices, invoice=invoice)
