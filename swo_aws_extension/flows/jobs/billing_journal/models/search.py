"""Billing charge search models."""

from dataclasses import dataclass
from typing import Literal


@dataclass
class SearchItem:
    """Billing charge search item."""

    criteria: str
    criteria_value: str


@dataclass
class SearchSource:
    """Billing charge search source."""

    type: Literal["Agreement", "Asset", "Subscription"]
    criteria: str
    criteria_value: str


@dataclass
class Search:
    """Billing charge search."""

    search_item: SearchItem
    source: SearchSource
