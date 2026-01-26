from http import HTTPStatus

import pytest
import responses
from requests import HTTPError

from swo_aws_extension.swo.auth import get_auth_token

OAUTH_URL = "https://oauth.test.com/token"


def test_get_auth_token_success(requests_mocker):
    expected_response = {
        "access_token": "test_token",
        "expires_in": 3600,
        "token_type": "Bearer",
    }
    requests_mocker.add(
        responses.POST,
        OAUTH_URL,
        json=expected_response,
        status=HTTPStatus.OK,
    )

    result = get_auth_token(
        endpoint=OAUTH_URL,
        client_id="test_client_id",
        client_secret="test_secret",  # noqa: S106
        scope="test_scope",
    )

    assert result == expected_response
    assert result["access_token"] == "test_token"


def test_get_auth_token_with_audience(requests_mocker):
    expected_response = {"access_token": "test_token", "expires_in": 3600}
    requests_mocker.add(
        responses.POST,
        OAUTH_URL,
        json=expected_response,
        status=HTTPStatus.OK,
    )

    result = get_auth_token(
        endpoint=OAUTH_URL,
        client_id="test_client_id",
        client_secret="test_secret",  # noqa: S106
        scope="test_scope",
        audience="test_audience",
    )

    assert result["access_token"] == "test_token"


def test_get_auth_token_http_error(requests_mocker):
    requests_mocker.add(
        responses.POST,
        OAUTH_URL,
        json={"error": "invalid_client"},
        status=HTTPStatus.UNAUTHORIZED,
    )

    with pytest.raises(HTTPError):
        get_auth_token(
            endpoint=OAUTH_URL,
            client_id="invalid_client",
            client_secret="invalid_secret",  # noqa: S106
            scope="test_scope",
        )


def test_get_auth_token_server_error(requests_mocker):
    requests_mocker.add(
        responses.POST,
        OAUTH_URL,
        json={"error": "server_error"},
        status=HTTPStatus.INTERNAL_SERVER_ERROR,
    )

    with pytest.raises(HTTPError):
        get_auth_token(
            endpoint=OAUTH_URL,
            client_id="test_client_id",
            client_secret="test_secret",  # noqa: S106
            scope="test_scope",
        )
