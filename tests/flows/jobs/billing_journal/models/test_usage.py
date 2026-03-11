from decimal import Decimal

from swo_aws_extension.flows.jobs.billing_journal.models.usage import (
    AccountUsage,
    OrganizationReport,
    OrganizationUsageResult,
    ServiceUsage,
)


def test_service_usage_default_decimal_values():
    result = ServiceUsage()

    assert result.marketplace == Decimal(0)
    assert result.usage == Decimal(0)
    assert result.support == Decimal(0)
    assert result.refund == Decimal(0)


def test_service_usage_default_optional_values():
    result = ServiceUsage()

    assert result.service_invoice_entity is None
    assert result.saving_plans == Decimal(0)
    assert result.provider_discount == Decimal(0)
    assert result.recurring == Decimal(0)


def test_service_usage_with_values():
    result = ServiceUsage(
        marketplace=Decimal("10.50"),
        service_invoice_entity="Amazon Web Services",
        usage=Decimal("100.00"),
        support=Decimal("5.00"),
    )

    assert result.marketplace == Decimal("10.50")
    assert result.service_invoice_entity == "Amazon Web Services"
    assert result.usage == Decimal("100.00")
    assert result.support == Decimal("5.00")


def test_account_usage_default_values():
    result = AccountUsage()

    assert result.services == {}


def test_account_usage_with_services():
    service = ServiceUsage(usage=Decimal("50.00"))

    result = AccountUsage(services={"AmazonEC2": service})

    assert "AmazonEC2" in result.services
    assert result.services["AmazonEC2"].usage == Decimal("50.00")


def test_organization_report_default_values():
    result = OrganizationReport()

    assert result.organization_data == {}
    assert result.accounts_data == {}


def test_organization_report_to_dict():
    report = OrganizationReport()
    report.organization_data["MARKETPLACE"] = [{"some": "data"}]
    report.accounts_data["ACT-1"] = {"SERVICE": [{"more": "data"}]}

    result = report.to_dict()

    assert result == {
        "organization_data": {"MARKETPLACE": [{"some": "data"}]},
        "accounts_data": {"ACT-1": {"SERVICE": [{"more": "data"}]}},
    }


def test_organization_usage_result_default_values():
    report = OrganizationReport()

    result = OrganizationUsageResult(reports=report)

    assert result.reports == report
    assert result.usage_by_account == {}


def test_organization_usage_result_with_usage():
    report = OrganizationReport()
    account_usage = AccountUsage(services={"S3": ServiceUsage()})

    result = OrganizationUsageResult(
        reports=report,
        usage_by_account={"ACT-1": account_usage},
    )

    assert result.reports == report
    assert "ACT-1" in result.usage_by_account
    assert "S3" in result.usage_by_account["ACT-1"].services
