import pytest

from swo_aws_extension.flows.jobs.billing_journal.generators.agreement import (
    AgreementJournalGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.journal_line import (
    JournalLineGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.usage import (
    CostExplorerUsageGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.models.journal_line import (
    JournalDetails,
    JournalLine,
)
from swo_aws_extension.flows.jobs.billing_journal.models.usage import (
    AccountUsage,
    OrganizationUsageResult,
)

MODULE = "swo_aws_extension.flows.jobs.billing_journal.generators.agreement"


@pytest.fixture
def mock_line_generator_cls(mocker):
    return mocker.patch(f"{MODULE}.JournalLineGenerator", autospec=True)


def test_run(mocker, mock_context, mock_line_generator_cls):
    agreement = {"id": "AGR-1", "externalIds": {"vendor": "MPA"}, "parameters": {"ordering": []}}
    mock_journal_line = mocker.MagicMock(spec=JournalLine)
    mock_generator_instance = mocker.MagicMock(spec=JournalLineGenerator)
    mock_generator_instance.generate.return_value = [mock_journal_line]
    mock_line_generator_cls.return_value = mock_generator_instance
    mock_account_usage = mocker.MagicMock(spec=AccountUsage)
    mock_usage_generator = mocker.MagicMock(spec=CostExplorerUsageGenerator)
    mock_usage_result = mocker.MagicMock(spec=OrganizationUsageResult)
    mock_usage_result.reports = {}
    mock_usage_result.usage_by_account = {"ACC-1": mock_account_usage}
    mock_usage_generator.run.return_value = mock_usage_result
    generator = AgreementJournalGenerator("USD", mock_context, mock_usage_generator)

    result = generator.run(agreement)

    assert result == [mock_journal_line]
    mock_generator_instance.generate.assert_called_once()
    call_args = mock_generator_instance.generate.call_args
    assert call_args[0][0] == "ACC-1"
    assert call_args[0][1] == mock_account_usage
    assert isinstance(call_args[0][2], JournalDetails)


def test_run_returns_empty_when_no_mpa_account(mocker, mock_context, mock_line_generator_cls):
    agreement = {"id": "AGR-1", "externalIds": {}, "parameters": {"ordering": []}}
    mock_usage_generator = mocker.MagicMock(spec=CostExplorerUsageGenerator)
    generator = AgreementJournalGenerator("USD", mock_context, mock_usage_generator)

    result = generator.run(agreement)

    assert result == []
    mock_usage_generator.run.assert_not_called()
    mock_line_generator_cls.assert_not_called()
