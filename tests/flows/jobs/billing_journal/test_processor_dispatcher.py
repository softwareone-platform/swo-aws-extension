from swo_aws_extension.flows.jobs.billing_journal.models.billing_period import BillingPeriod
from swo_aws_extension.flows.jobs.billing_journal.processor_dispatcher import (
    JournalProcessorDispatcher,
)


def test_build(mock_context):
    result = JournalProcessorDispatcher.build(mock_context.config)

    assert isinstance(result, JournalProcessorDispatcher)
    assert not result.has_processors


def test_build_with_params(mock_context):
    result = JournalProcessorDispatcher.build_with_params(mock_context.config, [{"key": "val"}])

    assert isinstance(result, JournalProcessorDispatcher)
    assert not result.has_processors


def test_process_all(mocker):
    first_processor = mocker.MagicMock()
    first_processor.process.return_value = [{"line": 1}]
    second_processor = mocker.MagicMock()
    second_processor.process.return_value = [{"line": 2}]
    dispatcher = JournalProcessorDispatcher([first_processor, second_processor])
    agreement = {"id": "AGR-1"}
    billing_period = BillingPeriod(start_date="2025-10-01", end_date="2025-11-01")

    result = dispatcher.process_all(agreement, billing_period)

    first_processor.process.assert_called_once_with(agreement, billing_period)
    second_processor.process.assert_called_once_with(agreement, billing_period)
    assert result == [{"line": 1}, {"line": 2}]


def test_has_processors():
    result = JournalProcessorDispatcher(["processor"])

    assert result.has_processors
