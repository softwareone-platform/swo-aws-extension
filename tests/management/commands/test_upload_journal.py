import json
from unittest.mock import mock_open

import pytest
from django.core.management import call_command
from requests import HTTPError, Response


@pytest.fixture
def journal_upload_response_data():
    return {
        "id": "BJO-0001-0005",
        "status": "Validating",
        "processing": {"total": 103, "ready": 0, "error": 0, "split": 0, "skipped": 103},
    }


def test_upload_journal_command(mocker):
    mocked_handle = mocker.patch(
        "swo_aws_extension.management.commands.upload_journal.Command.handle"
    )
    mocked_handle.return_value = None
    mocker.patch("builtins.open", mock_open(read_data="test content"))

    call_command("upload_journal", "test_file.txt", "--authorization", "AUT-123")

    mocked_handle.assert_called()


def test_upload_journal_command_with_journal_option(mocker):
    mocked_handle = mocker.patch(
        "swo_aws_extension.management.commands.upload_journal.Command.handle"
    )
    mocked_handle.return_value = None
    mocker.patch("builtins.open", mock_open(read_data="test content"))

    call_command("upload_journal", "--journal", "BJO-0001-0005", "test_file.txt")

    mocked_handle.assert_called()


def test_upload_journal_command_file_handling(mocker, mpt_client, journal_upload_response_data):
    mock_file = mock_open(read_data="journal data")
    mocker.patch("builtins.open", mock_file)

    create_mock = mocker.patch(
        "swo_mpt_api.billing.journal_client.JournalClient.create",
        return_value={"id": "BJO-0001-0005"},
    )
    upload_mock = mocker.patch(
        "swo_mpt_api.billing.journal_client.JournalClient.upload",
        return_value=journal_upload_response_data,
    )

    call_command(
        "upload_journal",
        "--authorization",
        "AUT-0001-0001",
        "journal_file.jsonl",
    )
    create_mock.assert_called()
    upload_mock.assert_called()


def test_upload_journal_command_file_handling_error_on_upload(mocker, mpt_client):
    mock_file = mock_open(read_data="journal data")
    mocker.patch("builtins.open", mock_file)

    create_mock = mocker.patch(
        "swo_mpt_api.billing.journal_client.JournalClient.create",
        return_value={"id": "BJO-0001-0005"},
    )

    error_response = Response()
    error_response.status_code = 400
    error_response._content = json.dumps({"error": True, "message": "Test error"}).encode("utf-8")
    upload_mock = mocker.patch(
        "swo_mpt_api.billing.journal_client.JournalClient.upload",
        side_effect=HTTPError(response=error_response),
    )
    get_mock = mocker.patch("swo_mpt_api.billing.journal_client.JournalClient.get")

    call_command(
        "upload_journal",
        "--journal",
        "BJO-0001-0001",
        "journal_file.jsonl",
    )
    create_mock.assert_not_called()
    upload_mock.assert_called()
    get_mock.assert_not_called()


def test_upload_journal_command_file_handling_error_on_create_journal(mocker, mpt_client):
    mock_file = mock_open(read_data="journal data")
    mocker.patch("builtins.open", mock_file)

    error_response = Response()
    error_response.status_code = 400
    error_response._content = json.dumps({"error": True, "message": "Test error"}).encode("utf-8")

    create_mock = mocker.patch(
        "swo_mpt_api.billing.journal_client.JournalClient.create",
        side_effect=HTTPError(response=error_response),
    )
    upload_mock = mocker.patch("swo_mpt_api.billing.journal_client.JournalClient.upload")

    call_command(
        "upload_journal",
        "--authorization",
        "AUT-0001-0001",
        "journal_file.jsonl",
    )
    create_mock.assert_called()
    upload_mock.assert_not_called()
