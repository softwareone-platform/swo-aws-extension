import pytest

from swo_aws_extension.constants import (
    ItemSkusEnum,
    UsageMetricTypeEnum,
)
from swo_aws_extension.flows.jobs.billing_journal.error import AWSBillingException
from swo_aws_extension.flows.jobs.billing_journal.item_journal_line import (
    GenerateItemJournalLines,
    GenerateJournalLines,
    GenerateOtherServicesJournalLines,
    GenerateSupportEnterpriseJournalLines,
    GenerateSupportJournalLines,
)


class DummyProcessor(GenerateItemJournalLines):
    def process(self, *args, **kwargs):
        payload = {
            "service_name": "TestService",
            "amount": 100.0,
        }
        raise AWSBillingException("Test error", payload=payload)


class DummyProcessorNotImplemented(GenerateItemJournalLines):
    def process(self, *args, **kwargs):
        super().process(*args, **kwargs)


def test_generate_item_journal_lines_process_not_implemented():
    """Test that NotImplementedError is raised when calling base process method."""
    base = DummyProcessorNotImplemented("metric", 1, 0)
    with pytest.raises(NotImplementedError):
        base.process("account_id", "item_external_id", {}, {}, {})


def test_generate_marketplace_journal_lines_process(mock_journal_args, mock_journal_line_factory):
    proc = GenerateJournalLines(
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
    proc = GenerateJournalLines(
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
    proc = GenerateJournalLines(
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
    """Test GenerateSupportJournalLines process."""
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
    """Test GenerateSupportEnterpriseJournalLines process."""
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
    proc = GenerateJournalLines(
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
    proc = GenerateJournalLines(
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


def test_support_two_charges_error(mock_journal_args, mock_journal_line_factory):
    """Test error when multiple support metrics are present."""
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

    with pytest.raises(AWSBillingException) as exc_info:
        proc.process(**args)

    assert (
        exc_info.value.message
        == "Multiple support metrics found: {'AWS Support (Enterprise)': 100.0,"
        " 'AWS Support (Business)': 100.0} with discount 35. "
    )
