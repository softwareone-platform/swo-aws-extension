from io import BytesIO

from swo_aws_extension.constants import BILLING_JOURNAL_SUCCESS_TITLE
from swo_aws_extension.flows.jobs.billing_journal.models.journal_line import JournalLine
from swo_aws_extension.swo.notifications.teams import Button

MODULE = "swo_aws_extension.flows.jobs.billing_journal.journal_manager"


def test_get_pending_journal_returns_existing(manager, mock_billing_client):
    mock_billing_client.journal.query().page.return_value = {
        "data": [{"id": "JRN-001", "name": "Test", "status": "Draft"}],
    }

    result = manager.get_pending_journal()  # act

    assert result.id == "JRN-001"


def test_get_pending_journal_returns_none_when_no_journals(manager, mock_billing_client):
    mock_billing_client.journal.query().page.return_value = {"data": []}

    result = manager.get_pending_journal()  # act

    assert result is None


def test_create_new_journal(manager, mock_billing_client):
    mock_billing_client.journal.query().page.return_value = {
        "$meta": {"pagination": {"total": 0}},
    }
    mock_billing_client.journal.create.return_value = {
        "id": "JRN-NEW",
        "name": "1 October 2025 #1",
    }

    result = manager.create_new_journal()  # act

    assert result.id == "JRN-NEW"
    expected_payload = {
        "name": "1 October 2025 #1",
        "authorization": {"id": "AUTH-123"},
        "dueDate": "2025-10-01",
        "externalIds": {"vendor": "AWS-2025-October"},
    }
    mock_billing_client.journal.create.assert_called_once_with(expected_payload)


def test_create_new_journal_increments_index(manager, mock_billing_client):
    mock_billing_client.journal.query().page.return_value = {
        "$meta": {"pagination": {"total": 1}},
    }
    mock_billing_client.journal.create.return_value = {
        "id": "JRN-NEW",
        "name": "1 October 2025 #2",
    }

    result = manager.create_new_journal()  # act

    assert result.id == "JRN-NEW"
    expected_payload = {
        "name": "1 October 2025 #2",
        "authorization": {"id": "AUTH-123"},
        "dueDate": "2025-10-01",
        "externalIds": {"vendor": "AWS-2025-October"},
    }
    mock_billing_client.journal.create.assert_called_once_with(expected_payload)


def test_upload_journal(mocker, manager, mock_billing_client, mock_context):
    line_mock = mocker.MagicMock(spec=JournalLine)
    line_mock.to_jsonl.return_value = '{"test": 1}\n'
    expected_bytesio = BytesIO(b'{"test": 1}\n{"test": 1}\n')
    mocker.patch(f"{MODULE}.BytesIO", return_value=expected_bytesio)
    expected_button = Button("Open journal JRN-123", "https://mpt.test/billing/journals/JRN-123")

    manager.upload_journal("JRN-123", [line_mock, line_mock])  # act

    mock_billing_client.journal.upload.assert_called_once_with(
        "JRN-123", expected_bytesio, "journal.jsonl"
    )
    mock_context.notifier.send_success.assert_called_once_with(
        BILLING_JOURNAL_SUCCESS_TITLE,
        "Billing journal JRN-123 uploaded for AUTH-123 with 2 lines.",
        button=expected_button,
    )
