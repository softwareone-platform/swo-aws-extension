import json
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any


# TODO: why do we need it here and /models/hints.py?
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
class SearchItem:
    """Billing charge search item."""

    criteria: str
    value: str  # noqa: WPS110


@dataclass
class SearchSubscription:
    """Billing charge search subscription."""

    criteria: str
    value: str  # noqa: WPS110


@dataclass
class Search:
    """Billing charge search."""

    item: SearchItem  # noqa: WPS110
    subscription: SearchSubscription


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
        journal_line = asdict(self)
        journal_line["externalIds"] = journal_line.pop("external_ids")
        journal_line["price"]["PPx1"] = journal_line["price"].pop("pp_x1")
        journal_line["price"]["UnitPP"] = journal_line["price"].pop("unit_pp")

        if self.error is None:
            journal_line.pop("error")
        return journal_line

    def is_valid(self) -> bool:
        """Check if the journal line is valid (no error)."""
        return self.error is None

    def to_jsonl(self) -> str:
        """Export as a single JSONL line."""
        return json.dumps(self.to_dict(), default=str) + "\n"

    @classmethod
    def build(cls, item_external_id, journal_details, invoice_details, quantity=1, segment="COM"):
        """
        Create a new journal line dictionary for billing purposes.

        Args:
            item_external_id (str): External item ID.
            journal_details (dict): Journal metadata.
            invoice_details (InvoiceDetails): Invoice details .
            quantity (int, optional): Quantity of the item. Defaults to 1.
            segment (str, optional): Segment for the journal line. Defaults to "COM".

        Returns:
            dict: Journal line dictionary.
        """
        return cls(
            description=Description(
                value1=invoice_details.service_name,
                value2=f"{invoice_details.account_id}/{invoice_details.invoice_entity}",
            ),
            external_ids=ExternalIds(
                invoice=invoice_details.invoice_id,
                reference=journal_details["agreement_id"],
                vendor=journal_details["mpa_id"],
            ),
            period=Period(
                start=journal_details["start_date"],
                end=journal_details["end_date"],
            ),
            price=Price(
                pp_x1=invoice_details.amount,
                unit_pp=invoice_details.amount,
            ),
            quantity=quantity,
            search=Search(
                item=SearchItem(
                    criteria="item.externalIds.vendor",
                    value=item_external_id or "Item Not Found",
                ),
                subscription=SearchSubscription(
                    criteria="subscription.externalIds.vendor",
                    value=invoice_details.account_id,
                ),
            ),
            segment=segment,
            error=invoice_details.error,
        )
