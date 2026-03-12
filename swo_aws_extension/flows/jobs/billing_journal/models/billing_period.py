"""Billing period model."""

import datetime as dt
from dataclasses import dataclass
from typing import Self

from swo_aws_extension.constants import COST_EXPLORER_DATE_FORMAT, MONTHS_PER_YEAR


@dataclass(frozen=True)
class BillingPeriod:
    """Represents a billing period with start and end dates."""

    start_date: str
    end_date: str

    @property
    def year(self) -> int:
        """Extract year from start_date."""
        return int(self.start_date.split("-")[0])

    @property
    def month(self) -> int:
        """Extract month from start_date."""
        return int(self.start_date.split("-")[1])

    @property
    def last_day(self) -> str:
        """Get the last day of the billing period (end_date - 1 day)."""
        end = dt.date.fromisoformat(self.end_date)
        last = end - dt.timedelta(days=1)
        return last.strftime(COST_EXPLORER_DATE_FORMAT)

    @classmethod
    def from_year_month(cls, year: int, month: int) -> Self:
        """Create a BillingPeriod from a year and month.

        Args:
            year: The billing year.
            month: The billing month (1-12).

        Returns:
            BillingPeriod with start_date as first of month and end_date as first of next month.
        """
        start_date = dt.date(year, month, 1)
        next_year = year + 1 if month == MONTHS_PER_YEAR else year
        next_month = 1 if month == MONTHS_PER_YEAR else month + 1
        end_date = dt.date(next_year, next_month, 1)
        return cls(
            start_date=start_date.strftime(COST_EXPLORER_DATE_FORMAT),
            end_date=end_date.strftime(COST_EXPLORER_DATE_FORMAT),
        )
