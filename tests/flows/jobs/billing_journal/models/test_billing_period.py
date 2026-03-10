import pytest

from swo_aws_extension.flows.jobs.billing_journal.models.billing_period import BillingPeriod

TEST_YEAR = 2025
NEXT_YEAR = 2026
MONTH_JANUARY = 1
MONTH_FEBRUARY = 2
MONTH_JUNE = 6
MONTH_OCTOBER = 10
MONTH_NOVEMBER = 11
MONTH_DECEMBER = 12


def test_from_year_month_regular_month():
    result = BillingPeriod.from_year_month(TEST_YEAR, MONTH_OCTOBER)

    assert result == BillingPeriod(start_date="2025-10-01", end_date="2025-11-01")


def test_from_year_month_december():
    result = BillingPeriod.from_year_month(TEST_YEAR, MONTH_DECEMBER)

    assert result == BillingPeriod(start_date="2025-12-01", end_date="2026-01-01")


def test_from_year_month_january():
    result = BillingPeriod.from_year_month(TEST_YEAR, MONTH_JANUARY)

    assert result == BillingPeriod(start_date="2025-01-01", end_date="2025-02-01")


@pytest.mark.parametrize(
    ("year", "month", "expected_start", "expected_end"),
    [
        (TEST_YEAR, MONTH_FEBRUARY, "2025-02-01", "2025-03-01"),
        (TEST_YEAR, MONTH_JUNE, "2025-06-01", "2025-07-01"),
        (NEXT_YEAR, MONTH_NOVEMBER, "2026-11-01", "2026-12-01"),
    ],
)
def test_from_year_month_parametrized(year, month, expected_start, expected_end):
    result = BillingPeriod.from_year_month(year, month)

    assert result.start_date == expected_start
    assert result.end_date == expected_end
