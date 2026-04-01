from http import HTTPStatus

import pytest
import responses

from swo_aws_extension.swo.base_client import OAuthSessionClient

BASE_CLIENT_MODULE = "swo_aws_extension.swo.base_client"
TEST_BASE_URL = "https://api.test.com/"
TEST_OAUTH_URL = "https://oauth.test.com/token"
TEST_CLIENT_SECRET = "client-secret"


@pytest.fixture
def mock_oauth_token(mocker):
    return mocker.patch(
        f"{BASE_CLIENT_MODULE}.get_auth_token",
        return_value={"access_token": "test-token", "expires_in": 3600},
    )


@pytest.fixture
def mock_api(requests_mocker):
    return requests_mocker


@pytest.fixture
def oauth_client():
    return OAuthSessionClient(
        oauth_url=TEST_OAUTH_URL,
        client_id="client-id",
        client_secret=TEST_CLIENT_SECRET,
        audience="audience",
        base_url="https://api.test.com",
    )


def test_normalize_base_url_adds_trailing_slash(oauth_client):
    result = oauth_client.base_url  # act

    assert result == "https://api.test.com/"


def test_normalize_base_url_keeps_trailing_slash():
    client = OAuthSessionClient(
        oauth_url=TEST_OAUTH_URL,
        client_id="id",
        client_secret=TEST_CLIENT_SECRET,
        audience="aud",
        base_url="https://api.test.com/",
    )

    result = client.base_url

    assert result == "https://api.test.com/"


def test_request_strips_leading_slash(oauth_client, mock_api, mock_oauth_token):
    mock_api.add(
        responses.GET,
        f"{TEST_BASE_URL}health",
        json={"status": "ok"},
        status=HTTPStatus.OK,
    )

    response = oauth_client.get("/health")  # act

    assert response.status_code == HTTPStatus.OK


def test_request_refreshes_token(oauth_client, mock_api, mock_oauth_token):
    mock_api.add(
        responses.GET,
        f"{TEST_BASE_URL}health",
        json={"status": "ok"},
        status=HTTPStatus.OK,
    )

    oauth_client.get("health")  # act

    mock_oauth_token.assert_called_once()
    assert oauth_client.headers["Authorization"] == "Bearer test-token"
    assert oauth_client.headers["User-Agent"] == "swo-extensions/1.0"


def test_token_not_refreshed_when_valid(oauth_client, mock_api, mock_oauth_token):
    mock_api.add(
        responses.GET,
        f"{TEST_BASE_URL}first",
        json={},
        status=HTTPStatus.OK,
    )
    mock_api.add(
        responses.GET,
        f"{TEST_BASE_URL}second",
        json={},
        status=HTTPStatus.OK,
    )
    oauth_client.get("first")

    oauth_client.get("second")  # act

    mock_oauth_token.assert_called_once()
