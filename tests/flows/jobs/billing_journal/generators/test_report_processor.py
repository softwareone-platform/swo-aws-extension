from decimal import Decimal

import pytest

from swo_aws_extension.flows.jobs.billing_journal.generators.report_processor import (
    ReportProcessor,
)


def build_report_group(keys: list, amount: str = "100.00") -> dict:
    """Factory function to create report groups for testing."""
    return {
        "Keys": keys,
        "Metrics": {"UnblendedCost": {"Amount": amount}},
    }


def build_report(groups: list[dict]) -> list[dict]:
    """Factory function to create reports for testing."""
    return [{"Groups": groups}]


@pytest.fixture
def processor():
    return ReportProcessor()


def test_extract_invoice_entities(processor):
    report = build_report([
        {"Keys": ["Amazon S3", "AWS Inc."]},
        {"Keys": ["Amazon EC2", "AWS EMEA"]},
        {"Keys": ["Amazon RDS"]},
    ])

    result = processor.extract_invoice_entities(report)

    assert result == {
        "Amazon S3": "AWS Inc.",
        "Amazon EC2": "AWS EMEA",
    }


def test_extract_invoice_entities_empty(processor):
    result = processor.extract_invoice_entities([])

    assert result == {}


def test_extract_metrics(processor):
    report = build_report([
        {"Keys": ["Amazon S3", "100.50"], "Metrics": {"UnblendedCost": {"Amount": "100.50"}}},
        {"Keys": ["Amazon EC2", "200.75"], "Metrics": {"UnblendedCost": {"Amount": "200.75"}}},
    ])

    result = processor.extract_metrics(report, "Amazon S3")

    assert result == {"100.50": Decimal("100.50")}


def test_extract_metrics_skips_zero_and_multiple_periods(processor):
    report = [
        {
            "Groups": [
                {
                    "Keys": ["Amazon S3", "amount"],
                    "Metrics": {"UnblendedCost": {"Amount": "100.00"}},
                }
            ]
        },
        {
            "Groups": [
                {
                    "Keys": ["Amazon S3", "amount"],
                    "Metrics": {"UnblendedCost": {"Amount": "0.0"}},
                }
            ]
        },
        {
            "Groups": [
                {
                    "Keys": ["Amazon S3", "amount"],
                    "Metrics": {"UnblendedCost": {"Amount": "50.00"}},
                }
            ]
        },
    ]

    result = processor.extract_metrics(report, "Amazon S3")

    assert result == {"amount": Decimal("50.00")}


def test_extract_metrics_comma_decimal(processor):
    report = build_report([
        {"Keys": ["Amazon S3", "100,50"], "Metrics": {"UnblendedCost": {"Amount": "100,50"}}}
    ])

    result = processor.extract_metrics(report, "Amazon S3")

    assert result == {"100,50": Decimal("100.50")}


def test_extract_all_metrics_by_record_type(processor):
    report = build_report([
        build_report_group(["Usage", "Amazon S3"], "100.00"),
        build_report_group(["Usage", "Amazon EC2"], "200.00"),
        build_report_group(["Support", "Amazon S3"], "10.00"),
    ])

    result = processor.extract_all_metrics_by_record_type(report)

    assert result == {
        "Usage": {
            "Amazon S3": Decimal("100.00"),
            "Amazon EC2": Decimal("200.00"),
        },
        "Support": {
            "Amazon S3": Decimal("10.00"),
        },
    }


def test_extract_all_metrics_skips_zero(processor):
    report = build_report([build_report_group(["Usage", "Amazon S3"], "0.0")])

    result = processor.extract_all_metrics_by_record_type(report)

    assert result == {}


def test_parse_group_metrics_valid(processor):
    group = build_report_group(["Usage", "Amazon S3"], "100.50")

    result = processor.parse_group_metrics(group)

    assert result == ("Usage", "Amazon S3", Decimal("100.50"))


def test_parse_group_metrics_single_key(processor):
    group = {"Keys": ["Amazon S3", "100.50"], "Metrics": {"UnblendedCost": {"Amount": "100.50"}}}

    result = processor.parse_group_metrics(group)

    assert result == ("Amazon S3", "100.50", Decimal("100.50"))


def test_parse_group_metrics_invalid_single_key(processor):
    group = {"Keys": ["Usage"]}

    result = processor.parse_group_metrics(group)

    assert result is None


def test_parse_group_metrics_invalid_zero_amount(processor):
    group = build_report_group(["Usage", "Amazon S3"], "0.0")

    result = processor.parse_group_metrics(group)

    assert result is None


def test_parse_group_metrics_invalid_missing_metrics(processor):
    group = {"Keys": ["Usage", "Amazon S3"]}

    result = processor.parse_group_metrics(group)

    assert result is None


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        ("100.50", Decimal("100.50")),
        ("100,50", Decimal("100.50")),
        ("100", Decimal(100)),
        ("0.0", Decimal(0)),
        ("-100.50", Decimal("-100.50")),
        ("1234567.89", Decimal("1234567.89")),
    ],
)
def test_parse_amount(processor, amount, expected):
    result = processor.parse_amount(amount)

    assert result == expected
