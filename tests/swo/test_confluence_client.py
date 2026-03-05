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


@pytest.fixture
def confluence_client(config):
    return ConfluenceClient(config)


@pytest.fixture
def mock_confluence(mocker):
    return mocker.patch(f"{MODULE}.Confluence", autospec=True)


def test_attach_content_success(confluence_client, mock_confluence, caplog):
    result = confluence_client.attach_content(
        page_id=PAGE_ID,
        filename=FILENAME,
        file_content=FILE_CONTENT,
        comment=COMMENT,
    )

    assert result is True
    mock_confluence.return_value.attach_content.assert_called_once_with(
        content=FILE_CONTENT,
        name=FILENAME,
        content_type=EXCEL_MIME_TYPE,
        page_id=PAGE_ID,
        comment=COMMENT,
    )
    assert f"File {FILENAME} attached to Confluence page {PAGE_ID}" in caplog.text


def test_attach_content_http_error_returns_false(
    confluence_client, mock_confluence, mocker, caplog
):
    mock_response = mocker.MagicMock(spec=requests.Response)
    mock_response.status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    mock_confluence.return_value.attach_content.side_effect = requests.HTTPError(
        response=mock_response
    )
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
    mock_confluence.return_value.attach_content.side_effect = requests.RequestException()
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

    mock_confluence.return_value.attach_content.assert_called_once_with(
        content=FILE_CONTENT,
        name=FILENAME,
        content_type=EXCEL_MIME_TYPE,
        page_id=PAGE_ID,
        comment="",
    )


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
