"""Billing charge search models."""

from dataclasses import dataclass


@dataclass
class SearchItem:
    """Billing charge search item."""

    criteria: str
    criteria_value: str


@dataclass
class SearchSubscription:
    """Billing charge search subscription."""

    criteria: str
    criteria_value: str


@dataclass
class Search:
    """Billing charge search."""

    search_item: SearchItem
    subscription: SearchSubscription
