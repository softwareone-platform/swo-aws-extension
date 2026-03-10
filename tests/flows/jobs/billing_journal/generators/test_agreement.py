import pytest

from swo_aws_extension.flows.jobs.billing_journal.generators.agreement import (
    AgreementJournalGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.models.billing_period import BillingPeriod
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
    generator = AgreementJournalGenerator("USD", mock_context)
    expected_period = BillingPeriod(start_date="2025-10-01", end_date="2025-11-01")

    result = generator.run(agreement)

    assert result == [{"line": 1}]
    mock_dispatcher_instance.process_all.assert_called_once_with(agreement, expected_period)
