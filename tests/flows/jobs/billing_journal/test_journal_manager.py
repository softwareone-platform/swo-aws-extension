from io import BytesIO
from typing import Any

import pytest
from requests import HTTPError

from swo_aws_extension.constants import BILLING_JOURNAL_SUCCESS_TITLE
from swo_aws_extension.flows.jobs.billing_journal.models.journal_line import JournalLine
from swo_aws_extension.flows.jobs.billing_journal.models.usage import OrganizationReport
from swo_aws_extension.swo.notifications.teams import Button

MODULE = "swo_aws_extension.flows.jobs.billing_journal.journal_manager"


def test_get_pending_journal_returns_existing(manager: Any, mock_billing_client: Any) -> None:
    mock_billing_client.journal.query().page.return_value = {
        "data": [{"id": "JRN-001", "name": "Test", "status": "Draft"}],
    }

    result = manager.get_pending_journal()  # act

    assert result.id == "JRN-001"


def test_get_pending_journal_returns_none_when_no_journals(
    manager: Any,
    mock_billing_client: Any,
) -> None:
    mock_billing_client.journal.query().page.return_value = {"data": []}

    result = manager.get_pending_journal()  # act

    assert result is None


def test_create_new_journal(manager: Any, mock_billing_client: Any) -> None:
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


def test_create_new_journal_increments_index(manager: Any, mock_billing_client: Any) -> None:
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


def test_upload_journal(mocker: Any, manager: Any, mock_billing_client: Any) -> None:
    line_mock = mocker.MagicMock(spec=JournalLine)
    line_mock.to_jsonl.return_value = '{"test": 1}\n'
    expected_bytesio = BytesIO(b'{"test": 1}\n{"test": 1}\n')
    mocker.patch(f"{MODULE}.BytesIO", return_value=expected_bytesio)

    manager.upload_journal("JRN-123", [line_mock, line_mock])  # act

    mock_billing_client.journal.upload.assert_called_once_with(
        "JRN-123", expected_bytesio, "journal.jsonl"
    )


@pytest.mark.parametrize("line_count", [0, 1, 3])
def test_upload_journal_dry_run(
    mocker: Any,
    manager_dry_run: Any,
    mock_billing_client: Any,
    mock_context: Any,
    line_count: int,
) -> None:
    line_mock = mocker.MagicMock(spec=JournalLine)
    line_mock.to_jsonl.return_value = '{"test": 1}\n'
    mock_logger = mocker.patch(f"{MODULE}.logger")
    lines = [line_mock] * line_count

    manager_dry_run.upload_journal("JRN-123", lines)  # act

    mock_billing_client.journal.upload.assert_not_called()
    mock_context.notifier.send_success.assert_not_called()
    assert mock_logger.info.call_count == 1 + line_count
    mock_logger.info.assert_any_call(
        "Dry run enabled. Skipping upload for journal %s (%d lines).",
        "JRN-123",
        line_count,
    )


def test_notify_success(manager: Any, mock_context: Any) -> None:
    expected_button = Button("Open journal JRN-123", "https://mpt.test/billing/journals/JRN-123")

    manager.notify_success("JRN-123", 2)  # act

    mock_context.notifier.send_success.assert_called_once_with(
        BILLING_JOURNAL_SUCCESS_TITLE,
        "Billing journal JRN-123 uploaded for AUTH-123 with 2 lines.",
        button=expected_button,
    )


def test_upload_attachments_uploads_report_with_data(
    mocker: Any,
    manager: Any,
    mock_billing_client: Any,
) -> None:
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


def test_upload_attachments_skips_empty_report(manager: Any, mock_billing_client: Any) -> None:
    report = OrganizationReport()

    manager.upload_attachments("JRN-001", {"AGR-1": report})  # act

    mock_billing_client.journal.attachments.assert_not_called()


def test_upload_attachments_logs_error_on_failure(
    manager: Any,
    mock_billing_client: Any,
) -> None:
    report = OrganizationReport(
        organization_data={"usage": [{"key": "value"}]},
    )
    mock_billing_client.journal.attachments("JRN-001").upload.side_effect = HTTPError("API error")

    manager.upload_attachments("JRN-001", {"AGR-1": report})  # act

    mock_billing_client.journal.attachments("JRN-001").upload.assert_called_once()
