from unittest.mock import MagicMock

from swo_aws_extension.constants import FAILED_TO_GET_SECRET
from swo_aws_extension.swo.ccp.client import CCPClient


def test_ccp_client_initialization(ccp_client, config):
    result = ccp_client

    assert result.config == config
    assert result.base_url == f"{config.ccp_api_base_url}/"


def test_ccp_client_url_without_trailing_slash(mocker):
    mock_config = MagicMock()
    mock_config.ccp_api_base_url = "https://api.example.com"
    mocker.patch(
        "swo_aws_extension.swo.ccp.client.OpenIDClient",
    )
    mocker.patch(
        "swo_aws_extension.swo.ccp.client.KeyVaultManager",
    )

    result = CCPClient(mock_config)

    assert result.base_url == "https://api.example.com/"


def test_refresh_secret_no_token(mocker, ccp_client):
    mocker.patch(
        "swo_aws_extension.swo.ccp.client.OpenIDClient.fetch_access_token",
        return_value=None,
    )

    result = ccp_client.refresh_secret()

    assert result is None


def test_refresh_secret_save_fails(
    mocker,
    requests_mocker,
    ccp_client,
    settings,
    mock_get_secret_response,
):
    client_id = settings.EXTENSION_CONFIG["CCP_CLIENT_ID"]
    mock_url = (
        f"{ccp_client.base_url}process/lighthouse/ad/retrieve/secret/{client_id}?api-version=v1"
    )
    requests_mocker.get(mock_url, json=mock_get_secret_response)
    mocker.patch(
        "swo_aws_extension.swo.ccp.client.OpenIDClient.fetch_access_token",
        return_value="credentials_token",
    )
    mocker.patch(
        "swo_aws_extension.swo.ccp.client.KeyVaultManager.save_secret",
        return_value=None,
    )

    result = ccp_client.refresh_secret()

    assert result is None


def test_refresh_secret_success(
    mocker,
    requests_mocker,
    ccp_client,
    settings,
    mock_get_secret_response,
):
    client_id = settings.EXTENSION_CONFIG["CCP_CLIENT_ID"]
    mock_url = (
        f"{ccp_client.base_url}process/lighthouse/ad/retrieve/secret/{client_id}?api-version=v1"
    )
    requests_mocker.get(mock_url, json=mock_get_secret_response)
    mocker.patch(
        "swo_aws_extension.swo.ccp.client.OpenIDClient.fetch_access_token",
        return_value="credentials_token",
    )
    mocker.patch(
        "swo_aws_extension.swo.ccp.client.KeyVaultManager.save_secret",
        return_value="new_secret",
    )

    result = ccp_client.refresh_secret()

    assert result == "new_secret"


def test_refresh_secret_api_returns_no_secret(
    mocker,
    requests_mocker,
    ccp_client,
    settings,
    caplog,
):
    client_id = settings.EXTENSION_CONFIG["CCP_CLIENT_ID"]
    mock_url = (
        f"{ccp_client.base_url}process/lighthouse/ad/retrieve/secret/{client_id}?api-version=v1"
    )
    requests_mocker.get(mock_url, json={})
    mocker.patch(
        "swo_aws_extension.swo.ccp.client.OpenIDClient.fetch_access_token",
        return_value="credentials_token",
    )
    mock_send_error = mocker.patch(
        "swo_aws_extension.swo.ccp.client.TeamsNotificationManager.send_error"
    )

    result = ccp_client.refresh_secret()

    assert result is None
    assert FAILED_TO_GET_SECRET in caplog.text
    mock_send_error.assert_called_once()
