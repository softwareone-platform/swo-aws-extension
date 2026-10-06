import pytest

from swo_aws_extension.flows.jobs.billing_validation.detail import (
    VALIDATION_DETAIL_HEADERS,
    build_validation_detail_rows,
)
from tests.flows.jobs.billing_validation.test_report import validations  # noqa: F401

SERVICE_DISCOUNT_PCT = 62.5
SERVICE_DISCOUNT_AMOUNT = -883.9


def test_build_validation_detail_rows_lists_steps_invoices_and_notes(validations):  # noqa: F811
    result = build_validation_detail_rows(validations[:1])

    rows = [dict(zip(VALIDATION_DETAIL_HEADERS, row, strict=True)) for row in result]
    assert [row["Type"] for row in rows] == ["Step", "Step", "Step", "Step", "Invoice"]
    assert [row["Description"] for row in rows[:4]] == [
        "AWS cost price (invoice total before tax)",
        "SPP discount kept by SWO",
        "Service discount 62.5% of SPP discount on usage",
        "Expected sales price",
    ]
    assert rows[2]["Percentage"] == pytest.approx(SERVICE_DISCOUNT_PCT)
    assert rows[2]["Amount"] == pytest.approx(SERVICE_DISCOUNT_AMOUNT)
    assert rows[4]["Invoice ID"] == "2847784289"


def test_build_validation_detail_rows_missing_invoices_has_no_steps(validations):  # noqa: F811
    result = build_validation_detail_rows(validations[-1:])

    assert result == []
