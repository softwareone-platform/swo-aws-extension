"""Billing journal models."""

from dataclasses import dataclass
from typing import Any


@dataclass
class Journal:
    """Represents a billing journal entity."""

    id: str
    name: str | None = None
    status: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Journal":
        """Instantiate a Journal from a dictionary representation."""
        return cls(
            id=payload.get("id", ""),
            name=payload.get("name"),
            status=payload.get("status"),
        )
