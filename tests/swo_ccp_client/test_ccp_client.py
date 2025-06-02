from unittest.mock import patch

import pytest
import requests.exceptions
from requests import Request
from requests.models import Response

from swo_aws_extension.aws.config import Config
from swo_aws_extension.constants import (
    ACCESS_TOKEN_NOT_FOUND_IN_RESPONSE,
    FAILED_TO_GET_SECRET,
    FAILED_TO_SAVE_SECRET_TO_KEY_VAULT,
)
from swo_ccp_client.client import CCPClient


@pytest.fixture()
def mock_get_token(mocker, mock_token):
    mock_get_token = mocker.patch("swo_ccp_client.client.get_openid_token")
    mock_get_token.return_value = {"access_token": mock_token}
    return mock_get_token


def test_get_ccp_access_token(ccp_client, config, mock_key_vault_secret_value, mock_get_token):
    token = ccp_client.get_ccp_access_token("oauth_scope")
    assert token == "test-token"
    mock_get_token.assert_called_once_with(
        endpoint=config.ccp_oauth_url,
        client_id=config.ccp_client_id,
        client_secret=mock_key_vault_secret_value,
        scope=config.ccp_oauth_scope,
    )


def test_get_ccp_access_token_with_no_secret(mocker, ccp_client_no_secret, config):
    token = ccp_client_no_secret.get_ccp_access_token("scope")
    assert token is None


def test_get_ccp_access_token_with_no_access_token(
    mocker,
    ccp_client,
    config,
    mock_key_vault_secret_value,
    caplog,
):
    with patch("swo_ccp_client.client.get_openid_token") as mock_get_token:
        mock_get_token.return_value = {}
        mocked_send_error = mocker.patch("swo_ccp_client.client.send_error")
        token = ccp_client.get_ccp_access_token("oauth_scope")
        assert token is None
        mock_get_token.assert_called_once_with(
            endpoint=config.ccp_oauth_url,
            client_id=config.ccp_client_id,
            client_secret=mock_key_vault_secret_value,
            scope=config.ccp_oauth_scope,
        )
        assert ACCESS_TOKEN_NOT_FOUND_IN_RESPONSE in caplog.text
        mocked_send_error.assert_called_once()


def test_onboard_customer(
    mocker, ccp_client, mock_onboard_customer_response, onboard_customer_factory
):
    mock_response = mocker.Mock(spec=Response)
    mock_response.json.return_value = mock_onboard_customer_response
    mock_response.status_code = 200
    mocker.patch.object(ccp_client, "post", return_value=mock_response)

    response = ccp_client.onboard_customer(onboard_customer_factory())
    assert response == mock_onboard_customer_response
    ccp_client.post.assert_called_once_with(
        url="/services/aws-essentials/customer?api-version=v2",
        json=onboard_customer_factory(),
    )


def test_get_onboard_status(mocker, ccp_client, onboard_customer_status_factory):
    ccp_engagement_id = "73ae391e-69de-472c-8d05-2f7feb173207"
    mock_response = mocker.Mock(spec=Response)
    mock_response.json.return_value = onboard_customer_status_factory()
    mock_response.status_code = 200
    mocker.patch.object(ccp_client, "get", return_value=mock_response)

    response = ccp_client.get_onboard_status(ccp_engagement_id)
    assert response == onboard_customer_status_factory()
    ccp_client.get.assert_called_once_with(
        url="services/aws-essentials/customer/engagement/"
        "73ae391e-69de-472c-8d05-2f7feb173207?api-version=v2"
    )


def test_get_secret(
    requests_mocker,
    settings,
    ccp_client,
    mock_get_secret_response,
    mock_token,
):
    api_url = ccp_client.base_url
    client_id = settings.EXTENSION_CONFIG["CCP_CLIENT_ID"]
    mock_retrieve_secret_url = (
        f"{api_url}process/lighthouse/ad/retrieve/secret/{client_id}?api-version=v1"
    )
    requests_mocker.get(
        mock_retrieve_secret_url,
        json=mock_get_secret_response,
    )
    secret = ccp_client.get_secret(mock_token)
    assert secret == mock_get_secret_response["clientSecret"]


def test_get_secret_no_client_secret(
    mocker,
    requests_mocker,
    settings,
    ccp_client,
    mock_token,
    caplog,
):
    api_url = ccp_client.base_url
    client_id = settings.EXTENSION_CONFIG["CCP_CLIENT_ID"]
    mock_retrieve_secret_url = (
        f"{api_url}process/lighthouse/ad/retrieve/secret/{client_id}?api-version=v1"
    )
    requests_mocker.get(
        mock_retrieve_secret_url,
        json={},
    )
    mocked_send_error = mocker.patch("swo_ccp_client.client.send_error")
    secret = ccp_client.get_secret(mock_token)
    assert secret is None
    assert FAILED_TO_GET_SECRET in caplog.text
    mocked_send_error.assert_called_once()


def test_get_secret_from_key_vault(mocker, mock_key_vault_secret_value, config, mock_get_token):
    mocker.patch(
        "mpt_extension_sdk.key_vault.base.KeyVault.get_secret",
        return_value=mock_key_vault_secret_value,
    )

    ccp_client = CCPClient(config)
    secret = ccp_client.get_secret_from_key_vault()
    assert secret == mock_key_vault_secret_value


def test_get_secret_from_key_vault_not_found(mocker, config, mock_get_token):
    mock_get_secret = mocker.patch(
        "mpt_extension_sdk.key_vault.base.KeyVault.get_secret",
        return_value=None,
    )

    mock_send_error = mocker.patch("swo_ccp_client.client.send_error", return_value=None)

    ccp_client = CCPClient(config)

    secret = ccp_client.get_secret_from_key_vault()

    assert secret is None
    assert mock_get_secret.call_count == 2
    assert mock_send_error.call_count == 2


def test_save_secret_to_key_vault(
    mocker,
    ccp_client,
    mock_key_vault_secret_value,
):
    mocker.patch(
        "mpt_extension_sdk.key_vault.base.KeyVault.set_secret",
        return_value=mock_key_vault_secret_value,
    )
    secret = ccp_client.save_secret_to_key_vault(mock_key_vault_secret_value)
    assert secret == mock_key_vault_secret_value


def test_save_secret_to_key_vault_not_saved(
    mocker,
    config,
    ccp_client,
    mock_key_vault_secret_value,
    caplog,
):
    mocked_send_error = mocker.patch("swo_ccp_client.client.send_error")
    mock_set_secret = mocker.patch(
        "mpt_extension_sdk.key_vault.base.KeyVault.set_secret",
        return_value=None,
    )
    secret = ccp_client.save_secret_to_key_vault(mock_key_vault_secret_value)
    assert secret is None
    mock_set_secret.assert_called_once_with(
        config.ccp_key_vault_secret_name,
        mock_key_vault_secret_value,
    )
    mocked_send_error.assert_called_once()
    assert FAILED_TO_SAVE_SECRET_TO_KEY_VAULT in caplog.text


def test_prepare_request(mocker):
    request = mocker.Mock(spec=Request)
    request.url = "/test_url"

    config = mocker.Mock()
    config.ccp_api_base_url = "https://localhost"

    parent_prepare_request = mocker.patch(
        "swo_ccp_client.client.Session.prepare_request", return_value="https://localhost"
    )
    join_url = mocker.patch(
        "swo_ccp_client.client.CCPClient._join_url", return_value="https://localhost"
    )
    mocker.patch("swo_ccp_client.client.CCPClient.get_ccp_access_token", return_value="auth-token")
    client = CCPClient(config)
    client.prepare_request(request)
    parent_prepare_request.assert_called_once()
    join_url.assert_called_once()


def test_join_url(mocker):
    mocker.patch("swo_ccp_client.client.CCPClient.get_ccp_access_token", return_value="auth-token")

    config = mocker.Mock()
    config.ccp_api_base_url = "https://localhost"
    client = CCPClient(config)
    assert client._join_url("/resource/12") == client._join_url("https://localhost/resource/12")
    assert client._join_url("resource/12") == client._join_url("https://localhost/resource/12")

    config = mocker.Mock()
    config.ccp_api_base_url = "https://localhost/"
    client = CCPClient(config)
    assert client._join_url("/resource/12") == client._join_url("https://localhost/resource/12")
    assert client._join_url("resource/12") == client._join_url("https://localhost/resource/12")


def test_request(mocker):
    mocker.patch("swo_ccp_client.client.CCPClient.get_ccp_access_token", return_value="auth-token")
    config = mocker.Mock()
    config.ccp_api_base_url = "https://localhost"
    client = CCPClient(config)

    response = mocker.Mock(spec=Response)
    response.status_code = 200
    response.json.return_value = {"key": "value"}
    request_mock = mocker.patch("swo_ccp_client.client.Session.request", return_value=response)
    mocker.patch("swo_ccp_client.client.CCPClient.get_ccp_access_token", return_value="auth-token")
    client.get_onboard_status("123")
    request_mock.assert_called_once()


def test_request_fail(mocker):
    mocker.patch(
        "swo_ccp_client.client.CCPClient.get_ccp_access_token",
        return_value="auth-token",
        spec=True
    )
    config = mocker.Mock()
    config.ccp_api_base_url = "https://localhost"
    client = CCPClient(config)

    response = mocker.Mock(spec=Response, )
    response.url = (
        "https://localhost/services/aws-essentials/customer/engagement/123?api-version=v2"
    )
    response.status_code = 200
    response.json.return_value = {"statusCode": 404, "message": "Not Found"}
    mocker.patch("swo_ccp_client.client.Session.request", return_value=response, spec=True)
    with pytest.raises(requests.exceptions.HTTPError) as exc_info:
        client.get_onboard_status("123")
    assert "404" in str(exc_info.value)
    assert "Not Found" in str(exc_info.value)


@pytest.mark.parametrize(
    ("url", "expected_value"),
    [
        ("https://test.vault.azure.net/secrets/test-secret", "test"),
        ("https://test.vault.azure.net", "test"),
        ("https://test.vault.azure.net/", "test"),
        ("https://test.vault.azure.net/secrets/", "test"),
        ("test", "test"),
    ],
)
def test_keyvault_url_parsing(url, expected_value, mocker, settings):
    mocker.patch("swo_ccp_client.client.CCPClient.get_ccp_access_token", return_value="auth-token")
    config = Config()
    client = CCPClient(config)

    key_vault_name = client._parse_keyvault_name_from_url(url)

    assert key_vault_name == expected_value


def test_refresh_secret_success(
    mocker,
    ccp_client,
    mock_key_vault_secret_value,
    mock_get_secret_response,
    mock_token,
    mock_get_token,
):
    mock_get_secret = mocker.patch.object(ccp_client, "get_secret")
    mock_get_secret.return_value = mock_get_secret_response["clientSecret"]
    mock_save_secret = mocker.patch.object(ccp_client, "save_secret_to_key_vault")
    mock_save_secret.return_value = mock_key_vault_secret_value

    result = ccp_client.refresh_secret()

    assert result == mock_key_vault_secret_value
    mock_get_token.assert_called_once_with(
        endpoint=ccp_client.config.ccp_oauth_url,
        client_id=ccp_client.config.ccp_client_id,
        client_secret=mock_key_vault_secret_value,
        scope=ccp_client.config.ccp_oauth_credentials_scope,
    )
    mock_get_secret.assert_called_once_with(mock_token)
    mock_save_secret.assert_called_once_with(mock_get_secret_response["clientSecret"])


def test_refresh_secret_no_access_token(
    mocker, ccp_client, mock_key_vault_secret_value, config, mock_get_token
):
    mock_get_token.return_value = {}
    mocked_send_error = mocker.patch("swo_ccp_client.client.send_error")

    result = ccp_client.refresh_secret()

    assert result is None
    mock_get_token.assert_called_once_with(
        endpoint=config.ccp_oauth_url,
        client_id=config.ccp_client_id,
        client_secret=mock_key_vault_secret_value,
        scope=config.ccp_oauth_credentials_scope,
    )
    mocked_send_error.assert_called_once()


def test_refresh_secret_no_secret(
    mocker, ccp_client, mock_key_vault_secret_value, mock_token, config, mock_get_token
):
    mock_get_secret = mocker.patch.object(ccp_client, "get_secret")
    mock_get_secret.return_value = None
    mocker.patch("swo_ccp_client.client.send_error")

    result = ccp_client.refresh_secret()

    assert result is None
    mock_get_token.assert_called_once_with(
        endpoint=config.ccp_oauth_url,
        client_id=config.ccp_client_id,
        client_secret=mock_key_vault_secret_value,
        scope=config.ccp_oauth_credentials_scope,
    )
    mock_get_secret.assert_called_once_with(mock_token)


def test_refresh_secret_not_saved(
    mocker,
    ccp_client,
    mock_key_vault_secret_value,
    mock_get_secret_response,
    mock_token,
    config,
    mock_get_token,
):
    mock_get_secret = mocker.patch.object(ccp_client, "get_secret")
    mock_get_secret.return_value = mock_get_secret_response["clientSecret"]
    mock_save_secret = mocker.patch.object(ccp_client, "save_secret_to_key_vault")
    mock_save_secret.return_value = None
    mocker.patch("swo_ccp_client.client.send_error")

    result = ccp_client.refresh_secret()

    assert result is None
    mock_get_token.assert_called_once_with(
        endpoint=config.ccp_oauth_url,
        client_id=config.ccp_client_id,
        client_secret=mock_key_vault_secret_value,
        scope=config.ccp_oauth_credentials_scope,
    )
    mock_get_secret.assert_called_once_with(mock_token)
    mock_save_secret.assert_called_once_with(mock_get_secret_response["clientSecret"])
