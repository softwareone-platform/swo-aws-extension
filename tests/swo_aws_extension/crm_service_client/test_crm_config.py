import pytest

from swo_aws_extension.crm_service_client.config import (
    CRMConfig,
    get_crm_access_token,
    get_service_client,
)


@pytest.fixture()
def mock_settings(settings):
    settings.EXTENSION_CONFIG = {
        "CRM_API_BASE_URL": "https://api.example.com",
        "CRM_OAUTH_URL": "https://auth.example.com",
        "CRM_CLIENT_ID": "client_id",
        "CRM_CLIENT_SECRET": "client_secret",
        "CRM_AUDIENCE": "audience",
    }
    return settings


def test_crm_config(mock_settings):
    config = CRMConfig()
    assert config.base_url == "https://api.example.com"
    assert config.oauth_url == "https://auth.example.com"
    assert config.client_id == "client_id"
    assert config.client_secret == "client_secret"
    assert config.audience == "audience"


def test_get_crm_access_token(mocker, mock_settings):
    openid_response = {"access_token": "test_token"}
    mock_get_openid_token = mocker.patch(
        "swo_aws_extension.crm_service_client.config.get_openid_token",
        return_value=openid_response,
    )
    mock_get_openid_token.return_value = {"access_token": "test_token"}
    token = get_crm_access_token()
    assert token == "test_token"
    mock_get_openid_token.assert_called_once_with(
        endpoint="https://auth.example.com",
        client_id="client_id",
        client_secret="client_secret",
        scope=None,
        audience="audience",
    )


def test_get_service_client(mocker, mock_settings):
    mocker.patch(
        "swo_aws_extension.crm_service_client.config.get_crm_access_token",
        return_value="test_token",
    )
    client = get_service_client()
    assert client.base_url == "https://api.example.com/"
    assert client.api_token == "test_token"
    another_client = get_service_client()
    assert client == another_client
