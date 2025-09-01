import json
from dataclasses import asdict, dataclass, field
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
    PPx1: float
    unitPP: float  # noqa: N815


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


# TODO: fix N815 here, makes no sense
@dataclass
class JournalLine:
    """Charge line."""
    description: Description
    externalIds: ExternalIds  # noqa: N815
    period: Period
    price: Price
    quantity: int
    search: Search
    segment: str
    error: str | None = field(default=None)

    def to_dict(self) -> dict[str, Any]:
        """Custom dict serialization."""
        data = asdict(self)
        if self.error is None:
            data.pop("error")
        return data

    def is_valid(self) -> bool:
        """Check if the journal line is valid (no error)."""
        return self.error is None

    def to_jsonl(self) -> str:
        """Export as a single JSONL line."""
        return json.dumps(self.to_dict()) + "\n"
