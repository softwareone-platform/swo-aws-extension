from decimal import Decimal

import pytest

from swo_aws_extension.flows.jobs.billing_journal.models.usage import (
    AccountUsage,
    OrganizationReport,
    OrganizationUsageResult,
    ServiceMetric,
)


@pytest.fixture
def metric():
    return ServiceMetric(
        service_name="Amazon S3",
        record_type="Usage",
        amount=Decimal("100.00"),
        invoice_entity="AWS Inc.",
    )


def test_service_metric_default_values():
    result = ServiceMetric(
        service_name="Amazon S3",
        record_type="Usage",
    )

    assert result.service_name == "Amazon S3"
    assert result.record_type == "Usage"
    assert result.amount == Decimal(0)
    assert result.invoice_entity is None
    assert result.invoice_id is None


def test_service_metric_with_values():
    result = ServiceMetric(
        service_name="Amazon S3",
        record_type="Usage",
        amount=Decimal("100.50"),
        invoice_entity="AWS Inc.",
        invoice_id="INV-001",
    )

    assert result.service_name == "Amazon S3"
    assert result.record_type == "Usage"
    assert result.amount == Decimal("100.50")
    assert result.invoice_entity == "AWS Inc."
    assert result.invoice_id == "INV-001"


def test_account_usage_default_and_add_metric(metric):
    account_usage = AccountUsage()

    account_usage.add_metric(metric)  # act

    assert len(account_usage.metrics) == 1
    assert account_usage.metrics[0] == metric


def test_account_usage_filter_metrics():
    metrics = [
        ServiceMetric(
            service_name="Amazon S3",
            record_type="Usage",
            amount=Decimal("100.00"),
        ),
        ServiceMetric(
            service_name="Amazon EC2",
            record_type="Usage",
            amount=Decimal("200.00"),
        ),
        ServiceMetric(
            service_name="Amazon S3",
            record_type="Support",
            amount=Decimal("10.00"),
        ),
    ]
    account_usage = AccountUsage(metrics=metrics)

    result = account_usage.get_metrics_by_record_type("Usage")

    assert len(result) == 2
    assert metrics[0] in result
    assert metrics[1] in result


def test_account_usage_get_metrics_by_service():
    metrics = [
        ServiceMetric(
            service_name="Amazon S3",
            record_type="Usage",
            amount=Decimal("100.00"),
        ),
        ServiceMetric(
            service_name="Amazon EC2",
            record_type="Usage",
            amount=Decimal("200.00"),
        ),
        ServiceMetric(
            service_name="Amazon S3",
            record_type="Support",
            amount=Decimal("10.00"),
        ),
    ]
    account_usage = AccountUsage(metrics=metrics)

    result = account_usage.get_metrics_by_service("Amazon S3")

    assert len(result) == 2
    assert metrics[0] in result
    assert metrics[2] in result


def test_organization_report():
    report = OrganizationReport()
    report.organization_data["MARKETPLACE"] = [{"some": "data"}]
    report.accounts_data["ACT-1"] = {"SERVICE": [{"more": "data"}]}

    result = report.to_dict()

    assert result == {
        "organization_data": {"MARKETPLACE": [{"some": "data"}]},
        "accounts_data": {"ACT-1": {"SERVICE": [{"more": "data"}]}},
    }


def test_organization_usage_result(metric):
    report = OrganizationReport()
    account_usage = AccountUsage(metrics=[metric])

    result = OrganizationUsageResult(
        reports=report,
        usage_by_account={"ACT-1": account_usage},
    )

    assert result.reports == report
    assert "ACT-1" in result.usage_by_account
    assert len(result.usage_by_account["ACT-1"].metrics) == 1
