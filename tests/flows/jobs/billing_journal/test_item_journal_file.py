from decimal import Decimal

import pytest

from swo_aws_extension.constants import (
    ItemSkusEnum,
    UsageMetricTypeEnum,
)
from swo_aws_extension.flows.jobs.billing_journal.error import AWSBillingError
from swo_aws_extension.flows.jobs.billing_journal.item_journal_line import (
    GenerateItemJournalLines,
    GenerateOtherServicesJournalLines,
    GenerateSavingPlansJournalLines,
    GenerateSupportEnterpriseJournalLines,
    GenerateSupportJournalLines,
    GenerateUsageJournalLines,
)


class DummyProcessor(GenerateItemJournalLines):
    """Dummy processor that raises billing exception."""

    def process(self, *args, **kwargs):
        """Start process."""
        payload = {
            "service_name": "TestService",
            "amount": 100.0,
        }
        raise AWSBillingError("Test error", payload=payload)


def test_generate_marketplace_journal_lines_process(mock_journal_args, mock_journal_line_factory):
    proc = GenerateUsageJournalLines(
        UsageMetricTypeEnum.MARKETPLACE.value, billing_discount_tolerance_rate=1, discount=0
    )
    external_id = ItemSkusEnum.AWS_MARKETPLACE.value
    args = mock_journal_args(external_id)

    result = proc.process(**args)
    journal_line = mock_journal_line_factory(
        service_name="Marketplace service",
        item_external_id=external_id,
    )
    assert result == [journal_line]


def test_generate_usage_journal_lines_process(mock_journal_args, mock_journal_line_factory):
    proc = GenerateUsageJournalLines(
        UsageMetricTypeEnum.USAGE.value, billing_discount_tolerance_rate=1, discount=7
    )
    external_id = ItemSkusEnum.AWS_USAGE.value
    args = mock_journal_args(external_id)
    result = proc.process(**args)
    journal_line = mock_journal_line_factory(
        service_name="Usage service",
        item_external_id=external_id,
    )
    assert result == [journal_line]


def test_generate_usage_incentivate_journal_lines_process(
    mock_journal_args, mock_journal_line_factory
):
    proc = GenerateUsageJournalLines(
        UsageMetricTypeEnum.USAGE.value, billing_discount_tolerance_rate=1, discount=12
    )
    external_id = ItemSkusEnum.AWS_USAGE_INCENTIVATE.value
    args = mock_journal_args(external_id)
    result = proc.process(**args)
    journal_line = mock_journal_line_factory(
        service_name="Usage service incentivate",
        item_external_id=external_id,
    )
    assert result == [journal_line]


def test_generate_other_services_journal_lines_process(
    mock_journal_args, mock_journal_line_factory
):
    """Test GenerateOtherServicesJournalLines process."""
    proc = GenerateOtherServicesJournalLines(
        UsageMetricTypeEnum.USAGE.value, billing_discount_tolerance_rate=1, discount=0
    )
    external_id = ItemSkusEnum.AWS_OTHER_SERVICES.value
    args = mock_journal_args(external_id)

    result = proc.process(**args)
    journal_line = mock_journal_line_factory(
        service_name="Other AWS services",
        item_external_id=external_id,
    )
    assert result == [journal_line]


def test_generate_support_journal_lines_process(mock_journal_args, mock_journal_line_factory):
    proc = GenerateSupportJournalLines(
        UsageMetricTypeEnum.SUPPORT.value, billing_discount_tolerance_rate=1, discount=7
    )
    external_id = ItemSkusEnum.AWS_SUPPORT.value
    args = mock_journal_args(external_id)
    args["account_metrics"][UsageMetricTypeEnum.SUPPORT.value] = {"AWS Support (Business)": 100.0}
    args["account_metrics"][UsageMetricTypeEnum.REFUND.value] = {"refund": 7}

    result = proc.process(**args)
    journal_line = mock_journal_line_factory(
        service_name="AWS Support (Business)",
        item_external_id=external_id,
    )
    assert result == [journal_line]


def test_generate_support_enterprise_journal_lines_process(
    mock_journal_args, mock_journal_line_factory
):
    proc = GenerateSupportEnterpriseJournalLines(
        UsageMetricTypeEnum.SUPPORT.value, billing_discount_tolerance_rate=1, discount=35
    )
    item_external_id = ItemSkusEnum.AWS_SUPPORT_ENTERPRISE.value
    args = mock_journal_args(item_external_id)
    args["account_metrics"][UsageMetricTypeEnum.SUPPORT.value] = {"AWS Support (Enterprise)": 100.0}
    args["account_metrics"][UsageMetricTypeEnum.PROVIDER_DISCOUNT.value] = {
        "AWS Support (Enterprise)": 35
    }

    result = proc.process(**args)
    journal_line = mock_journal_line_factory(
        service_name="AWS Support (Enterprise)",
        item_external_id=item_external_id,
    )
    assert result == [journal_line]


def test_generate_recurring_lines_process(mock_journal_args, mock_journal_line_factory):
    proc = GenerateUsageJournalLines(
        UsageMetricTypeEnum.RECURRING.value, billing_discount_tolerance_rate=1, discount=7
    )
    item_external_id = ItemSkusEnum.UPFRONT.value
    args = mock_journal_args(item_external_id)
    result = proc.process(**args)
    journal_line = mock_journal_line_factory(
        service_name="Upfront service",
        item_external_id=item_external_id,
    )
    assert result == [journal_line]


def test_generate_recurring_incentivate_journal_lines_process(
    mock_journal_args, mock_journal_line_factory
):
    proc = GenerateUsageJournalLines(
        UsageMetricTypeEnum.RECURRING.value, billing_discount_tolerance_rate=1, discount=12
    )
    item_external_id = ItemSkusEnum.UPFRONT_INCENTIVATE.value
    args = mock_journal_args(item_external_id)
    result = proc.process(**args)
    journal_line = mock_journal_line_factory(
        service_name="Upfront service incentivate",
        item_external_id=item_external_id,
    )
    assert result == [journal_line]


def test_generate_item_journal_line_not_implemented(mock_journal_args, mock_journal_line_factory):
    proc = GenerateItemJournalLines(
        UsageMetricTypeEnum.MARKETPLACE.value, billing_discount_tolerance_rate=1, discount=0
    )
    external_id = ItemSkusEnum.AWS_MARKETPLACE.value
    args = mock_journal_args(external_id)

    result = proc.process(**args)
    journal_line = mock_journal_line_factory(
        service_name="Marketplace service",
        item_external_id=external_id,
    )
    assert result == [journal_line]


def test_generate_item_journal_line_process_with_error(mock_journal_args):
    proc = DummyProcessor(
        UsageMetricTypeEnum.MARKETPLACE.value, billing_discount_tolerance_rate=1, discount=0
    )
    external_id = ItemSkusEnum.AWS_MARKETPLACE.value
    args = mock_journal_args(external_id)

    with pytest.raises(AWSBillingError):
        proc.process(**args)


def test_generate_usage_journal_lines_process_no_amount(
    mock_journal_args, mock_journal_line_factory
):
    proc = GenerateUsageJournalLines(
        UsageMetricTypeEnum.MARKETPLACE.value, billing_discount_tolerance_rate=1, discount=0
    )
    external_id = ItemSkusEnum.AWS_MARKETPLACE.value
    args = mock_journal_args(external_id)
    args["account_metrics"][UsageMetricTypeEnum.MARKETPLACE.value] = {}

    result = proc.process(**args)
    assert result == []


def test_generate_support_journal_lines_no_support_metric(
    mock_journal_args, mock_journal_line_factory
):
    proc = GenerateSupportJournalLines(
        UsageMetricTypeEnum.SUPPORT.value, billing_discount_tolerance_rate=1, discount=7
    )
    external_id = ItemSkusEnum.AWS_SUPPORT.value
    args = mock_journal_args(external_id)
    args["account_metrics"][UsageMetricTypeEnum.SUPPORT.value] = {}
    args["account_metrics"][UsageMetricTypeEnum.REFUND.value] = {"refund": 7}

    result = proc.process(**args)

    assert result == []


def test_generate_support_journal_lines_no_refund_metric(
    mock_journal_args, mock_journal_line_factory
):
    proc = GenerateSupportJournalLines(
        UsageMetricTypeEnum.SUPPORT.value, billing_discount_tolerance_rate=1, discount=7
    )
    external_id = ItemSkusEnum.AWS_SUPPORT.value
    args = mock_journal_args(external_id)
    args["account_metrics"][UsageMetricTypeEnum.SUPPORT.value] = {"AWS Support (Business)": 100.0}
    args["account_metrics"][UsageMetricTypeEnum.REFUND.value] = {}

    result = proc.process(**args)
    assert result == []


def test_generate_support_enterprise_journal_lines_no_provider_discount(
    mock_journal_args, mock_journal_line_factory
):
    proc = GenerateSupportEnterpriseJournalLines(
        UsageMetricTypeEnum.SUPPORT.value, billing_discount_tolerance_rate=1, discount=35
    )
    item_external_id = ItemSkusEnum.AWS_SUPPORT_ENTERPRISE.value
    args = mock_journal_args(item_external_id)
    args["account_metrics"][UsageMetricTypeEnum.SUPPORT.value] = {"AWS Support (Enterprise)": 100.0}
    args["account_metrics"][UsageMetricTypeEnum.PROVIDER_DISCOUNT.value] = {}

    result = proc.process(**args)
    assert result == []


def test_generate_support_enterprise_journal_lines_no_support_metric(
    mock_journal_args, mock_journal_line_factory
):
    proc = GenerateSupportEnterpriseJournalLines(
        UsageMetricTypeEnum.SUPPORT.value, billing_discount_tolerance_rate=1, discount=35
    )
    item_external_id = ItemSkusEnum.AWS_SUPPORT_ENTERPRISE.value
    args = mock_journal_args(item_external_id)
    args["account_metrics"][UsageMetricTypeEnum.SUPPORT.value] = {}
    args["account_metrics"][UsageMetricTypeEnum.PROVIDER_DISCOUNT.value] = {
        "AWS Support (Enterprise)": 35
    }

    result = proc.process(**args)

    assert result == []


def test_support_two_charges_error(mock_journal_args, mock_journal_line_factory):
    proc = GenerateSupportEnterpriseJournalLines(
        UsageMetricTypeEnum.SUPPORT.value, billing_discount_tolerance_rate=1, discount=35
    )
    item_external_id = ItemSkusEnum.AWS_SUPPORT_ENTERPRISE.value
    args = mock_journal_args(item_external_id)
    args["account_metrics"][UsageMetricTypeEnum.SUPPORT.value] = {
        "AWS Support (Enterprise)": 100.0,
        "AWS Support (Business)": 100.0,
    }
    args["account_metrics"][UsageMetricTypeEnum.PROVIDER_DISCOUNT.value] = {
        "AWS Support (Enterprise)": 35
    }

    with pytest.raises(AWSBillingError) as exc_info:
        proc.process(**args)

    assert (
        exc_info.value.message
        == "Multiple support metrics found: {'AWS Support (Enterprise)': 100.0,"
        " 'AWS Support (Business)': 100.0} with discount 35. "
    )


def test_generate_journal_line_with_exchange_rate(mock_journal_args, mock_journal_line_factory):
    proc = GenerateUsageJournalLines(
        UsageMetricTypeEnum.MARKETPLACE.value, billing_discount_tolerance_rate=1, discount=0
    )
    external_id = ItemSkusEnum.AWS_MARKETPLACE.value
    args = mock_journal_args(external_id)
    args["account_invoices"]["invoice_entities"] = {
        "AWS Entity": {
            "invoice_id": "INV-123",
            "payment_currency_code": "EUR",
            "base_currency_code": "USD",
            "exchange_rate": Decimal("1.2"),
        }
    }
    args["account_metrics"][UsageMetricTypeEnum.SERVICE_INVOICE_ENTITY.value] = {
        "Marketplace service": "AWS Entity"
    }

    result = proc.process(**args)
    journal_line = mock_journal_line_factory(
        service_name="Marketplace service",
        item_external_id=external_id,
        price=120.0,
        invoice_id="INV-123",
        invoice_entity="AWS Entity",
    )
    assert result == [journal_line]


def test_default_discount_validator_no_match(mock_journal_args):
    proc = GenerateUsageJournalLines(
        UsageMetricTypeEnum.USAGE.value, billing_discount_tolerance_rate=1, discount=7
    )
    external_id = ItemSkusEnum.AWS_USAGE.value
    args = mock_journal_args(external_id)
    args["account_metrics"][UsageMetricTypeEnum.PROVIDER_DISCOUNT.value] = {"Usage service": 15}

    result = proc.process(**args)
    assert result == []


def test_generate_saving_plans_journal_lines_process(mock_journal_args, mock_journal_line_factory):
    proc = GenerateSavingPlansJournalLines(
        UsageMetricTypeEnum.SAVING_PLANS.value, billing_discount_tolerance_rate=1, discount=7
    )
    external_id = ItemSkusEnum.SAVING_PLANS_RECURRING_FEE.value
    args = mock_journal_args(external_id)
    args["account_metrics"][UsageMetricTypeEnum.SAVING_PLANS.value] = {"Saving plan service": 100.0}
    args["account_metrics"][UsageMetricTypeEnum.PROVIDER_DISCOUNT.value] = {
        "Saving plan service": 7
    }
    result = proc.process(**args)
    journal_line = mock_journal_line_factory(
        service_name="Saving plan service",
        item_external_id=external_id,
    )
    assert result == [journal_line]


def test_generate_saving_plans_journal_lines_process_invalid_discount(
    mock_journal_args, mock_journal_line_factory
):
    proc = GenerateSavingPlansJournalLines(
        UsageMetricTypeEnum.SAVING_PLANS.value, billing_discount_tolerance_rate=1, discount=7
    )
    external_id = ItemSkusEnum.SAVING_PLANS_RECURRING_FEE.value
    args = mock_journal_args(external_id)
    args["account_metrics"][UsageMetricTypeEnum.SAVING_PLANS.value] = {"Saving plan service": 100.0}
    args["account_metrics"][UsageMetricTypeEnum.PROVIDER_DISCOUNT.value] = {
        "Saving plan service": 3
    }
    result = proc.process(**args)
    assert result == []
