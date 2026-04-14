from io import BytesIO

from requests import HTTPError

from swo_aws_extension.constants import BILLING_JOURNAL_SUCCESS_TITLE
from swo_aws_extension.flows.jobs.billing_journal.models.journal_line import JournalLine
from swo_aws_extension.flows.jobs.billing_journal.models.usage import OrganizationReport
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
        "name": "1 October 2025 BT #1",
    }

    result = manager.create_new_journal()  # act

    assert result.id == "JRN-NEW"
    expected_payload = {
        "name": "1 October 2025 BT #1",
        "authorization": {"id": "AUTH-123"},
        "dueDate": "2025-10-01",
        "externalIds": {"vendor": "AWS-2025-October-BT"},
    }
    mock_billing_client.journal.create.assert_called_once_with(expected_payload)


def test_create_new_journal_increments_index(manager, mock_billing_client):
    mock_billing_client.journal.query().page.return_value = {
        "$meta": {"pagination": {"total": 1}},
    }
    mock_billing_client.journal.create.return_value = {
        "id": "JRN-NEW",
        "name": "1 October 2025 BT #2",
    }

    result = manager.create_new_journal()  # act

    assert result.id == "JRN-NEW"
    expected_payload = {
        "name": "1 October 2025 BT #2",
        "authorization": {"id": "AUTH-123"},
        "dueDate": "2025-10-01",
        "externalIds": {"vendor": "AWS-2025-October-BT"},
    }
    mock_billing_client.journal.create.assert_called_once_with(expected_payload)


def test_upload_journal(mocker, manager, mock_billing_client):
    line_mock = mocker.MagicMock(spec=JournalLine)
    line_mock.to_jsonl.return_value = '{"test": 1}\n'
    expected_bytesio = BytesIO(b'{"test": 1}\n{"test": 1}\n')
    mocker.patch(f"{MODULE}.BytesIO", return_value=expected_bytesio)

    manager.upload_journal("JRN-123", [line_mock, line_mock])  # act

    mock_billing_client.journal.upload.assert_called_once_with(
        "JRN-123", expected_bytesio, "journal.jsonl"
    )


def test_notify_success(manager, mock_context):
    expected_button = Button("Open journal JRN-123", "https://mpt.test/billing/journals/JRN-123")

    manager.notify_success("JRN-123", 2)  # act

    mock_context.notifier.send_success.assert_called_once_with(
        BILLING_JOURNAL_SUCCESS_TITLE,
        "Billing journal JRN-123 uploaded for AUTH-123 with 2 lines.",
        button=expected_button,
    )


def test_upload_attachments_uploads_report_with_data(mocker, manager, mock_billing_client):
    report = OrganizationReport(
        organization_data={"usage": [{"key": "value"}]},
        accounts_data={},
    )
    expected_bytesio = mocker.MagicMock(spec=BytesIO)
    mocker.patch(f"{MODULE}.BytesIO", return_value=expected_bytesio)

    manager.upload_attachments("JRN-001", {"AGR-1": report})  # act

    mock_billing_client.journal.attachments("JRN-001").upload.assert_called_once_with(
        filename="AGR-1.json",
        mimetype="application/json",
        file=expected_bytesio,
        attachment=mocker.ANY,
    )


def test_upload_attachments_skips_empty_report(manager, mock_billing_client):
    report = OrganizationReport()

    manager.upload_attachments("JRN-001", {"AGR-1": report})  # act

    mock_billing_client.journal.attachments.assert_not_called()


def test_upload_attachments_logs_error_on_failure(manager, mock_billing_client):
    report = OrganizationReport(
        organization_data={"usage": [{"key": "value"}]},
    )
    mock_billing_client.journal.attachments("JRN-001").upload.side_effect = HTTPError("API error")

    manager.upload_attachments("JRN-001", {"AGR-1": report})  # act

    mock_billing_client.journal.attachments("JRN-001").upload.assert_called_once()
