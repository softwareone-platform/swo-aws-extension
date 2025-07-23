import json

from ninja import Schema


class Error(Schema):
    id: str
    message: str


from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Description:
    value1: str
    value2: str


@dataclass
class ExternalIds:
    invoice: str
    reference: str
    vendor: str


@dataclass
class Period:
    start: str
    end: str


@dataclass
class Price:
    PPx1: float
    unitPP: float


@dataclass
class SearchItem:
    criteria: str
    value: str


@dataclass
class SearchSubscription:
    criteria: str
    value: str


@dataclass
class Search:
    item: SearchItem
    subscription: SearchSubscription


@dataclass
class JournalLine:
    description: Description
    externalIds: ExternalIds
    period: Period
    price: Price
    quantity: int
    search: Search
    segment: str
    error: str | None = field(default=None)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.error is None:
            data.pop("error")
        return data

    def is_valid(self) -> bool:
        return self.error is None

    def to_jsonl(self) -> str:
        """Export as a single JSONL line."""
        return json.dumps(self.to_dict()) + "\n"
