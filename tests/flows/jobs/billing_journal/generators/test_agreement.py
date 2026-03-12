import pytest

from swo_aws_extension.flows.jobs.billing_journal.generators.agreement import (
    AgreementJournalGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.usage import (
    CostExplorerUsageGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.models.billing_period import BillingPeriod
from swo_aws_extension.flows.jobs.billing_journal.models.usage import OrganizationUsageResult
from swo_aws_extension.flows.jobs.billing_journal.processor_dispatcher import (
    JournalProcessorDispatcher,
)

MODULE = "swo_aws_extension.flows.jobs.billing_journal.generators.agreement"


@pytest.fixture
def mock_dispatcher_cls(mocker):
    return mocker.patch(f"{MODULE}.JournalProcessorDispatcher", autospec=True)


def test_run(mocker, mock_context, mock_dispatcher_cls):
    agreement = {"id": "AGR-1", "externalIds": {"vendor": "MPA"}, "parameters": []}
    mock_dispatcher_instance = mocker.MagicMock(spec=JournalProcessorDispatcher)
    mock_dispatcher_instance.process_all.return_value = [{"line": 1}]
    mock_dispatcher_cls.build_with_params.return_value = mock_dispatcher_instance
    mock_usage_generator = mocker.MagicMock(spec=CostExplorerUsageGenerator)
    mock_usage_result = mocker.MagicMock(spec=OrganizationUsageResult)
    mock_usage_result.reports = {}
    mock_usage_result.usage_by_account = {}
    mock_usage_generator.run.return_value = mock_usage_result
    generator = AgreementJournalGenerator("USD", mock_context, mock_usage_generator)
    expected_period = BillingPeriod(start_date="2025-10-01", end_date="2025-11-01")

    result = generator.run(agreement)

    assert result == [{"line": 1}]
    mock_dispatcher_instance.process_all.assert_called_once_with(agreement, expected_period)


def test_run_returns_empty_when_no_mpa_account(mocker, mock_context, mock_dispatcher_cls):
    agreement = {"id": "AGR-1", "externalIds": {}, "parameters": []}
    mock_usage_generator = mocker.MagicMock(spec=CostExplorerUsageGenerator)
    generator = AgreementJournalGenerator("USD", mock_context, mock_usage_generator)

    result = generator.run(agreement)

    assert result == []
    mock_usage_generator.run.assert_not_called()
    mock_dispatcher_cls.build_with_params.assert_not_called()
