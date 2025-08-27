import json
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any


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
    value: str


@dataclass
class SearchSubscription:
    """Billing charge search subscription."""

    criteria: str
    value: str


@dataclass
class Search:
    """Billing charge search."""

    item: SearchItem
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
        data = asdict(self)
        data["externalIds"] = data.pop("external_ids")
        data["price"]["PPx1"] = data["price"].pop("pp_x1")
        data["price"]["UnitPP"] = data["price"].pop("unit_pp")

        if self.error is None:
            data.pop("error")
        return data

    def is_valid(self) -> bool:
        """Check if the journal line is valid (no error)."""
        return self.error is None

    def to_jsonl(self) -> str:
        """Export as a single JSONL line."""
        return json.dumps(self.to_dict(), default=str) + "\n"
