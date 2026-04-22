from http import HTTPStatus
from unittest.mock import MagicMock

import pytest
import requests

from swo_aws_extension.swo.openid.client import (
    DEFAULT_TOKEN_EXPIRY,
    TOKEN_EXPIRY_BUFFER,
    OpenIDClient,
    Token,
)
from swo_aws_extension.swo.openid.errors import (
    OpenIDHttpError,
    OpenIDSecretNotFoundError,
)

TOKEN_EXPIRY_SECONDS = DEFAULT_TOKEN_EXPIRY
CUSTOM_TOKEN_EXPIRY = 7200


@pytest.fixture
def openid_client(config):
    return OpenIDClient(config)


def test_token_initialization():
    result = Token("test_access_token", expires_in=TOKEN_EXPIRY_SECONDS)

    assert result.access_token == "test_access_token"


def test_token_initialization_default_expiry(mocker):
    mock_time = mocker.patch("swo_aws_extension.swo.openid.client.time")
    mock_time.time.return_value = 1000

    result = Token("test_access_token")

    assert result.token_expiry == 1000 + DEFAULT_TOKEN_EXPIRY


def test_token_initialization_custom_expiry(mocker):
    mock_time = mocker.patch("swo_aws_extension.swo.openid.client.time")
    mock_time.time.return_value = 1000

    result = Token("test_access_token", expires_in=CUSTOM_TOKEN_EXPIRY)

    assert result.token_expiry == 1000 + CUSTOM_TOKEN_EXPIRY


def test_token_is_not_expired_when_valid(mocker):
    mock_time = mocker.patch("swo_aws_extension.swo.openid.client.time")
    mock_time.time.return_value = 1000
    token = Token("test_access_token", expires_in=TOKEN_EXPIRY_SECONDS)

    result = token.is_expired()

    assert result is False


def test_token_is_expired_at_expiry_time(mocker):
    mock_time = mocker.patch("swo_aws_extension.swo.openid.client.time")
    mock_time.time.return_value = 1000
    token = Token("test_access_token", expires_in=TOKEN_EXPIRY_SECONDS)
    mock_time.time.return_value = 1000 + TOKEN_EXPIRY_SECONDS

    result = token.is_expired()

    assert result is True


def test_token_is_expired_within_buffer(mocker):
    mock_time = mocker.patch("swo_aws_extension.swo.openid.client.time")
    mock_time.time.return_value = 1000
    token = Token("test_access_token", expires_in=TOKEN_EXPIRY_SECONDS)
    mock_time.time.return_value = 1000 + TOKEN_EXPIRY_SECONDS - TOKEN_EXPIRY_BUFFER

    result = token.is_expired()

    assert result is True


def test_token_is_not_expired_before_buffer(mocker):
    mock_time = mocker.patch("swo_aws_extension.swo.openid.client.time")
    mock_time.time.return_value = 1000
    token = Token("test_access_token", expires_in=TOKEN_EXPIRY_SECONDS)
    mock_time.time.return_value = 1000 + TOKEN_EXPIRY_SECONDS - TOKEN_EXPIRY_BUFFER - 1

    result = token.is_expired()

    assert result is False


def test_fetch_access_token_success(mocker, openid_client):
    mocker.patch(
        "swo_aws_extension.swo.openid.client.KeyVaultManager.get_secret",
        return_value="client_secret",
    )
    mocker.patch(
        "swo_aws_extension.swo.openid.client.get_auth_token",
        return_value={"access_token": "new_token", "expires_in": 3600},
    )

    result = openid_client.fetch_access_token("test_scope")

    assert result == "new_token"


def test_fetch_access_token_returns_cached_token(mocker, openid_client):
    mocker.patch(
        "swo_aws_extension.swo.openid.client.KeyVaultManager.get_secret",
        return_value="client_secret",
    )
    mock_get_token = mocker.patch(
        "swo_aws_extension.swo.openid.client.get_auth_token",
        return_value={"access_token": "new_token", "expires_in": 3600},
    )

    result = openid_client.fetch_access_token("test_scope")

    second_result = openid_client.fetch_access_token("test_scope")
    assert result == "new_token"
    assert second_result == "new_token"
    mock_get_token.assert_called_once()


def test_fetch_access_token_no_secret_error(mocker, openid_client):
    mocker.patch(
        "swo_aws_extension.swo.openid.client.KeyVaultManager.get_secret",
        return_value=None,
    )
    mocker.patch("swo_aws_extension.swo.openid.client.TeamsNotificationManager.send_error")

    with pytest.raises(OpenIDSecretNotFoundError):
        openid_client.fetch_access_token("test_scope")


def test_fetch_access_token_http_error(mocker, openid_client):
    mocker.patch(
        "swo_aws_extension.swo.openid.client.KeyVaultManager.get_secret",
        return_value="client_secret",
    )
    mock_response = MagicMock()
    mock_response.status_code = HTTPStatus.UNAUTHORIZED
    mock_response.text = "Unauthorized"
    http_error = requests.HTTPError(response=mock_response)
    mocker.patch(
        "swo_aws_extension.swo.openid.client.get_auth_token",
        side_effect=http_error,
    )
    mocker.patch("swo_aws_extension.swo.openid.client.TeamsNotificationManager.send_error")

    with pytest.raises(OpenIDHttpError) as exc_info:
        openid_client.fetch_access_token("test_scope")

    assert exc_info.value.status_code == HTTPStatus.UNAUTHORIZED


def test_fetch_token_notifies_on_secret_error(mocker, openid_client):
    mocker.patch(
        "swo_aws_extension.swo.openid.client.KeyVaultManager.get_secret",
        return_value=None,
    )
    mock_send_error = mocker.patch(
        "swo_aws_extension.swo.openid.client.TeamsNotificationManager.send_error"
    )

    with pytest.raises(OpenIDSecretNotFoundError):
        openid_client.fetch_access_token("test_scope")

    mock_send_error.assert_called_once()


def test_fetch_token_notifies_on_http_error(mocker, openid_client):
    mocker.patch(
        "swo_aws_extension.swo.openid.client.KeyVaultManager.get_secret",
        return_value="client_secret",
    )
    mock_response = MagicMock()
    mock_response.status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    mock_response.text = "Server Error"
    http_error = requests.HTTPError(response=mock_response)
    mocker.patch(
        "swo_aws_extension.swo.openid.client.get_auth_token",
        side_effect=http_error,
    )
    mock_send_error = mocker.patch(
        "swo_aws_extension.swo.openid.client.TeamsNotificationManager.send_error"
    )

    with pytest.raises(OpenIDHttpError):
        openid_client.fetch_access_token("test_scope")

    mock_send_error.assert_called_once()
