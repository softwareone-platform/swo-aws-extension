"""Cell formatting helpers shared by the validation sheets."""

from decimal import Decimal


def amount(total: Decimal | None) -> float | str:
    """Excel cell for an optional amount: a float, or empty when unknown."""
    if total is None:
        return ""
    return float(total)
