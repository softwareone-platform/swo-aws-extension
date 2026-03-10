import pytest

from swo_aws_extension.constants import BILLING_JOURNAL_ERROR_TITLE
from swo_aws_extension.flows.jobs.billing_journal.generators.agreement import (
    AgreementJournalGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.authorization import (
    AuthorizationJournalGenerator,
)

MODULE = "swo_aws_extension.flows.jobs.billing_journal.generators.authorization"


@pytest.fixture
def authorization():
    return {"id": "AUTH-1", "currency": "USD", "externalIds": {"vendor": "MPA-123"}}


@pytest.fixture
def mock_get_agreements(mocker):
    return mocker.patch(f"{MODULE}.get_agreements_by_query", autospec=True)


@pytest.fixture
def mock_agreement_generator_cls(mocker):
    return mocker.patch(f"{MODULE}.AgreementJournalGenerator", autospec=True)


def test_no_agreements_returns_empty_list(
    mock_context,
    mock_get_agreements,
    mock_agreement_generator_cls,
    authorization,
):
    mock_get_agreements.return_value = []
    generator = AuthorizationJournalGenerator(mock_context)

    result = generator.run(authorization)

    assert result == []
    mock_agreement_generator_cls.assert_not_called()


def test_processes_agreements(
    mocker,
    mock_context,
    mock_get_agreements,
    mock_agreement_generator_cls,
    authorization,
):
    mock_get_agreements.return_value = [{"id": "AGR-1"}, {"id": "AGR-2"}]
    mock_agr_gen = mocker.MagicMock(spec=AgreementJournalGenerator)
    mock_agr_gen.run.return_value = [{"line": 1}]
    mock_agreement_generator_cls.return_value = mock_agr_gen
    generator = AuthorizationJournalGenerator(mock_context)

    result = generator.run(authorization)

    assert mock_agr_gen.run.call_count == 2
    assert result == [{"line": 1}, {"line": 1}]


def test_exception_sends_error(
    mocker,
    mock_context,
    mock_get_agreements,
    mock_agreement_generator_cls,
    authorization,
):
    mock_get_agreements.return_value = [{"id": "AGR-1"}]
    mock_agr_gen = mocker.MagicMock(spec=AgreementJournalGenerator)
    mock_agr_gen.run.side_effect = Exception("Test Error")
    mock_agreement_generator_cls.return_value = mock_agr_gen
    generator = AuthorizationJournalGenerator(mock_context)

    result = generator.run(authorization)

    assert result == []
    expected_message = "Failed to generate billing journal for AGR-1: Test Error"
    mock_context.notifier.send_error.assert_called_once_with(
        BILLING_JOURNAL_ERROR_TITLE, expected_message
    )
