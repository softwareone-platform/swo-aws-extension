import json
from unittest.mock import mock_open

import pytest
from django.core.management import CommandError, call_command
from requests import HTTPError, Response


def test_upload_journal_attachment_command(mocker):
    mocked_handle = mocker.patch(
        "swo_aws_extension.management.commands.upload_journal_attachment.Command.handle"
    )
    mocked_handle.return_value = None

    call_command("upload_journal_attachment", "BJO-3828-0982", "test_file.txt")
    mocked_handle.assert_called()


def test_upload_file(mocker, tmp_path):
    file = tmp_path / "file1.txt"
    file.write_text("content1")
    journal_id = "JRN-123"
    mocker.patch("builtins.open", mock_open(read_data="test content"))

    upload_mock = mocker.patch("swo_mpt_api.billing.journal_client.AttachmentsClient.upload")
    call_command("upload_journal_attachment", journal_id, str(file))
    upload_mock.assert_called_once_with(mocker.ANY, "application/octet-stream")


def test_upload_zip_file(mocker, tmp_path):
    test_folder = tmp_path / "test_folder"
    test_folder.mkdir()
    (test_folder / "file1.txt").write_text("content1")
    (test_folder / "file2.txt").write_text("content2")

    journal_id = "JRN-123"
    upload_mock = mocker.patch("swo_mpt_api.billing.journal_client.AttachmentsClient.upload")
    call_command("upload_journal_attachment", journal_id, test_folder)
    upload_mock.assert_called_once()


def test_upload_file_fail(mocker, tmp_path):
    file = tmp_path / "file1.txt"
    file.write_text("content1")
    journal_id = "JRN-123"
    mocker.patch("builtins.open", mock_open(read_data="test content"))

    error_response = Response()
    error_response.status_code = 400
    error_response._content = json.dumps({"error": True, "message": "Test error"}).encode("utf-8")

    mocker.patch(
        "swo_mpt_api.billing.journal_client.AttachmentsClient.upload",
        side_effect=HTTPError(response=error_response),
    )
    with pytest.raises(CommandError):
        call_command("upload_journal_attachment", journal_id, file)


def test_upload_zip_file_fail(mocker, tmp_path):
    test_folder = tmp_path / "test_folder"
    test_folder.mkdir()
    (test_folder / "file1.txt").write_text("content1")
    (test_folder / "file2.txt").write_text("content2")

    journal_id = "JRN-123"
    error_response = Response()
    error_response.status_code = 400
    error_response._content = json.dumps({"error": True, "message": "Test error"}).encode("utf-8")

    mocker.patch(
        "swo_mpt_api.billing.journal_client.AttachmentsClient.upload",
        side_effect=HTTPError(response=error_response),
    )

    with pytest.raises(CommandError):
        call_command("upload_journal_attachment", journal_id, str(test_folder))


def test_upload_non_existing_path_fail(mocker):
    journal_id = "JRN-123"
    with pytest.raises(CommandError):
        call_command("upload_journal_attachment", journal_id, "/tmp/non-existing-folder")
