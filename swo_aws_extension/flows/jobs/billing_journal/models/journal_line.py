"""Billing journal line models."""

import json
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any, Self

from swo_aws_extension.flows.jobs.billing_journal.models.search import (
    Search,
    SearchItem,
    SearchSource,
)


@dataclass
class Description:
    """Billing journal description."""

    value1: str
    value2: str


@dataclass
class ExternalIds:
    """Billing journal external ids."""

    invoice: str
    reference: str
    vendor: str


@dataclass
class Period:
    """Billing journal period."""

    start: str
    end: str


@dataclass
class Price:
    """Billing journal price."""

    pp_x1: Decimal
    unit_pp: Decimal


@dataclass
class JournalDetails:
    """Journal metadata details."""

    agreement_id: str
    mpa_id: str
    start_date: str
    end_date: str


@dataclass
class InvoiceDetails:
    """Details specific to an invoice line."""

    item_sku: str
    service_name: str
    amount: Decimal
    account_id: str
    invoice_entity: str
    start_date: str
    end_date: str
    invoice_id: str = ""
    error: str | None = None


@dataclass
class JournalLine:
    """Charge line."""

    description: Description
    external_ids: ExternalIds
    period: Period
    price: Price
    quantity: int
    search: Search
    segment: str
    error: str | None = field(default=None)

    def to_dict(self) -> dict[str, Any]:
        """Custom dict serialization."""
        line_payload = asdict(self)
        line_payload["externalIds"] = line_payload.pop("external_ids")
        line_payload["price"]["PPx1"] = line_payload["price"].pop("pp_x1")
        line_payload["price"]["UnitPP"] = line_payload["price"].pop("unit_pp")

        search_data = line_payload.pop("search")
        search_data["item"] = search_data.pop("search_item")
        search_data["item"]["value"] = search_data["item"].pop("criteria_value")
        search_data["source"]["value"] = search_data["source"].pop("criteria_value")
        line_payload["search"] = search_data

        if self.error is None:
            line_payload.pop("error")
        return line_payload

    def is_valid(self) -> bool:
        """Check if the journal line is valid (no error)."""
        return self.error is None

    def to_jsonl(self) -> str:
        """Export as a single JSONL line."""
        json_dump = json.dumps(self.to_dict(), default=str)
        return f"{json_dump}\n"

    @classmethod
    def build(
        cls,
        item_external_id: str | None,
        journal_details: JournalDetails,
        invoice_details: InvoiceDetails,
        quantity: int = 1,
        segment: str = "COM",
    ) -> Self:
        """Create a new journal line for billing purposes.

        Args:
            item_external_id: External item ID.
            journal_details: Journal metadata.
            invoice_details: Invoice details.
            quantity: Quantity of the item. Defaults to 1.
            segment: Segment for the journal line. Defaults to "COM".

        Returns:
            JournalLine: Journal line object.
        """
        return cls(
            description=Description(
                value1=invoice_details.service_name,
                value2=f"{invoice_details.account_id}/{invoice_details.invoice_entity}",
            ),
            external_ids=ExternalIds(
                invoice=invoice_details.invoice_id,
                reference=journal_details.agreement_id,
                vendor=journal_details.mpa_id,
            ),
            period=Period(
                start=invoice_details.start_date,
                end=invoice_details.end_date,
            ),
            price=Price(
                pp_x1=invoice_details.amount,
                unit_pp=invoice_details.amount,
            ),
            quantity=quantity,
            search=Search(
                search_item=SearchItem(
                    criteria="item.externalIds.vendor",
                    criteria_value=item_external_id or "Item Not Found",
                ),
                source=SearchSource(
                    type="Subscription",
                    criteria="externalIds.vendor",
                    criteria_value=journal_details.mpa_id,
                ),
            ),
            segment=segment,
            error=invoice_details.error,
        )
