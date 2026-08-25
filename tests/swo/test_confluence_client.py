from http import HTTPStatus

import pytest
import requests

from swo_aws_extension.constants import EXCEL_MIME_TYPE
from swo_aws_extension.swo.confluence_client import ConfluenceClient

MODULE = "swo_aws_extension.swo.confluence_client"

PAGE_ID = "123456"
FILENAME = "report.xlsx"
FILE_CONTENT = b"file content"
COMMENT = "Total orders 5"
ATTACHMENT_PATH = f"rest/api/content/{PAGE_ID}/child/attachment"
EXISTING_ATTACHMENT_ID = "att-1"


def expected_headers():
    return {"X-Atlassian-Token": "no-check", "Accept": "application/json"}


def expected_data(comment=COMMENT):
    return {
        "type": "attachment",
        "fileName": FILENAME,
        "contentType": EXCEL_MIME_TYPE,
        "comment": comment,
        "minorEdit": "true",
    }


@pytest.fixture
def confluence_client(config):
    return ConfluenceClient(config)


@pytest.fixture
def mock_confluence(mocker):
    mock_class = mocker.patch(f"{MODULE}.Confluence", autospec=True)
    mock_class.return_value.get.return_value = {"results": []}
    return mock_class


def test_attach_content_success(confluence_client, mock_confluence, caplog):
    result = confluence_client.attach_content(
        page_id=PAGE_ID,
        filename=FILENAME,
        file_content=FILE_CONTENT,
        comment=COMMENT,
    )

    assert result is True
    mock_confluence.return_value.post.assert_called_once_with(
        path=ATTACHMENT_PATH,
        data=expected_data(),
        headers=expected_headers(),
        files={"file": (FILENAME, FILE_CONTENT, EXCEL_MIME_TYPE)},
    )
    assert f"File {FILENAME} attached to Confluence page {PAGE_ID}" in caplog.text


def test_attach_content_looks_up_existing_attachment(confluence_client, mock_confluence):
    confluence_client.attach_content(
        page_id=PAGE_ID,
        filename=FILENAME,
        file_content=FILE_CONTENT,
        comment=COMMENT,
    )  # act

    mock_confluence.return_value.get.assert_called_once_with(
        path=ATTACHMENT_PATH,
        headers=expected_headers(),
        params={"filename": FILENAME},
    )


def test_attach_content_replaces_existing_attachment(confluence_client, mock_confluence):
    mock_confluence.return_value.get.return_value = {"results": [{"id": EXISTING_ATTACHMENT_ID}]}

    confluence_client.attach_content(
        page_id=PAGE_ID,
        filename=FILENAME,
        file_content=FILE_CONTENT,
        comment=COMMENT,
    )  # act

    post_call = mock_confluence.return_value.post.call_args
    assert post_call.kwargs["path"] == f"{ATTACHMENT_PATH}/{EXISTING_ATTACHMENT_ID}/data"


def test_attach_content_http_error_returns_false(
    confluence_client, mock_confluence, mocker, caplog
):
    mock_response = mocker.MagicMock(spec=requests.Response)
    mock_response.status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    mock_confluence.return_value.post.side_effect = requests.HTTPError(response=mock_response)
    expected_message = "Confluence HTTP error"

    result = confluence_client.attach_content(
        page_id=PAGE_ID,
        filename=FILENAME,
        file_content=FILE_CONTENT,
        comment=COMMENT,
    )

    assert result is False
    assert expected_message in caplog.text


def test_attach_content_request_exception_returns_false(confluence_client, mock_confluence, caplog):
    mock_confluence.return_value.post.side_effect = requests.RequestException()
    expected_message = "Confluence request error"

    result = confluence_client.attach_content(
        page_id=PAGE_ID,
        filename=FILENAME,
        file_content=FILE_CONTENT,
        comment=COMMENT,
    )

    assert result is False
    assert expected_message in caplog.text


def test_attach_content_default_comment(confluence_client, mock_confluence):
    confluence_client.attach_content(
        page_id=PAGE_ID,
        filename=FILENAME,
        file_content=FILE_CONTENT,
    )  # act

    post_call = mock_confluence.return_value.post.call_args
    assert post_call.kwargs["data"] == expected_data(comment=f"Uploaded {FILENAME}.")


def test_client_uses_config_credentials(confluence_client, mock_confluence, config):
    confluence_client.attach_content(
        page_id=PAGE_ID,
        filename=FILENAME,
        file_content=FILE_CONTENT,
    )  # act

    mock_confluence.assert_called_once_with(
        url=config.confluence_base_url,
        username=config.confluence_user,
        password=config.confluence_token,
        cloud=True,
    )
