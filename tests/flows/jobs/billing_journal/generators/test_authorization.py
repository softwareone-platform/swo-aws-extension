from typing import Any

import pytest

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.constants import BILLING_JOURNAL_ERROR_TITLE
from swo_aws_extension.flows.jobs.billing_journal.generators.agreement import (
    AgreementJournalGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.authorization import (
    AuthorizationJournalGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.models.journal_line import JournalLine
from swo_aws_extension.flows.jobs.billing_journal.models.journal_result import (
    AgreementJournalResult,
    AuthorizationJournalResult,
)

MODULE = "swo_aws_extension.flows.jobs.billing_journal.generators.authorization"


@pytest.fixture
def authorization() -> dict[str, Any]:
    return {"id": "AUTH-1", "currency": "USD", "externalIds": {"operations": "MPA-123"}}


@pytest.fixture
def mock_get_agreements(mocker: Any) -> Any:
    return mocker.patch(f"{MODULE}.get_agreements_by_query", autospec=True)


@pytest.fixture
def mock_agreement_generator_cls(mocker: Any) -> Any:
    return mocker.patch(f"{MODULE}.AgreementJournalGenerator", autospec=True)


@pytest.fixture
def mock_aws_client_cls(mocker: Any) -> Any:
    mock = mocker.patch(f"{MODULE}.AWSClient", autospec=True)
    mock.return_value = mocker.MagicMock(spec=AWSClient)
    mock.return_value.account_id = "MPA-123"
    return mock


def test_no_agreements_returns_empty_list(
    mock_context: Any,
    mock_get_agreements: Any,
    mock_agreement_generator_cls: Any,
    mock_aws_client_cls: Any,
    authorization: dict[str, Any],
) -> None:
    mock_get_agreements.return_value = []
    generator = AuthorizationJournalGenerator(mock_context)

    result = generator.run(authorization)

    assert result == AuthorizationJournalResult()
    mock_agreement_generator_cls.assert_not_called()
    mock_aws_client_cls.assert_not_called()


def test_processes_agreements(
    mocker: Any,
    mock_context: Any,
    mock_get_agreements: Any,
    mock_agreement_generator_cls: Any,
    mock_aws_client_cls: Any,
    authorization: dict[str, Any],
) -> None:
    mock_get_agreements.return_value = [{"id": "AGR-1"}, {"id": "AGR-2"}]
    mock_journal_line = mocker.MagicMock(spec=JournalLine)
    mock_agr_gen = mocker.MagicMock(spec=AgreementJournalGenerator)
    mock_agr_gen.run.return_value = AgreementJournalResult(lines=[mock_journal_line])
    mock_agreement_generator_cls.return_value = mock_agr_gen
    generator = AuthorizationJournalGenerator(mock_context)

    result = generator.run(authorization)

    assert mock_agr_gen.run.call_count == 2
    assert result.lines == [mock_journal_line, mock_journal_line]
    mock_agreement_generator_cls.assert_called_once_with(
        "USD",
        mock_context,
        mock_aws_client_cls.return_value,
        mock_aws_client_cls.return_value.account_id,
    )


def test_exception_sends_error(
    mocker: Any,
    mock_context: Any,
    mock_get_agreements: Any,
    mock_agreement_generator_cls: Any,
    mock_aws_client_cls: Any,
    authorization: dict[str, Any],
) -> None:
    mock_get_agreements.return_value = [{"id": "AGR-1"}]
    mock_agr_gen = mocker.MagicMock(spec=AgreementJournalGenerator)
    test_error = AWSError("Test Error")
    mock_agr_gen.run.side_effect = test_error
    mock_agreement_generator_cls.return_value = mock_agr_gen
    generator = AuthorizationJournalGenerator(mock_context)

    result = generator.run(authorization)

    assert result == AuthorizationJournalResult()
    expected_message = "Failed to generate billing journal for AGR-1: Test Error"
    mock_context.notifier.send_error.assert_called_once_with(
        BILLING_JOURNAL_ERROR_TITLE, expected_message
    )
