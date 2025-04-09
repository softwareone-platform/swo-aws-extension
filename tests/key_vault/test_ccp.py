import pymsteams

from swo_aws_extension.constants import ACCESS_TOKEN_NOT_FOUND_IN_RESPONSE
from swo_aws_extension.key_vault.ccp import (
    get_ccp_openid_secret,
    refresh_ccp_openid_secret,
)


def test_get_valid_openid_token(
    mocker,
    mock_key_vault_secret_value,
):
    """
    Test the get_openid_token function with a valid token.
    """
    mocker.patch(
        "mpt_extension_sdk.key_vault.base.KeyVault.get_secret",
        return_value=mock_key_vault_secret_value,
    )
    test_token = get_ccp_openid_secret()
    assert test_token == mock_key_vault_secret_value


def test_get_valid_openid_token_no_secret(
    mocker,
    settings,
):
    """
    Test the get_openid_token function no secret value returned.
    """
    settings.EXTENSION_CONFIG["MSTEAMS_WEBHOOK_URL"] = "https://teams.webhook"
    mocker.patch(
        "mpt_extension_sdk.key_vault.base.KeyVault.get_secret",
        return_value=None,
    )
    mocked_message = mocker.MagicMock()
    mocked_message.send.side_effect = pymsteams.TeamsWebhookException("error")

    mocker.patch(
        "swo_aws_extension.notifications.pymsteams.connectorcard",
        return_value=mocked_message,
    )

    test_token = get_ccp_openid_secret()
    assert test_token is None


def test_refresh_ccp_openid_token(
    mocker,
    requests_mocker,
    settings,
    mock_key_vault_secret_value,
    mock_valid_access_token_response,
    mock_oauth_post_url,
    mock_get_secret_response,
):
    """
    Test the refresh_ccp_openid_token function.
    """
    api_url = settings.EXTENSION_CONFIG["CCP_MPT_API_URL"]
    client_id = settings.EXTENSION_CONFIG["CCP_CLIENT_ID"]
    mock_url = f"https://{api_url}/process/lighthouse/ad/retrieve/secret/{client_id}?api-version=v1"

    requests_mocker.get(
        mock_url,
        json=mock_get_secret_response,
    )
    requests_mocker.post(
        mock_oauth_post_url,
        json=mock_valid_access_token_response,
    )
    mocker.patch(
        "mpt_extension_sdk.key_vault.base.KeyVault.get_secret",
        return_value=mock_key_vault_secret_value,
    )
    mocker.patch(
        "mpt_extension_sdk.key_vault.base.KeyVault.set_secret",
        return_value=mock_key_vault_secret_value,
    )
    test_secret = refresh_ccp_openid_secret()
    assert test_secret == mock_key_vault_secret_value


def test_refresh_ccp_openid_token_with_request_exception(
    mocker,
    requests_mocker,
    settings,
    mock_key_vault_secret_value,
    mock_oauth_post_url,
    caplog,
):
    """
    Test the refresh_ccp_openid_token function with a request exception.
    """
    settings.EXTENSION_CONFIG["MSTEAMS_WEBHOOK_URL"] = "https://teams.webhook"
    mocked_message = mocker.MagicMock()
    mocked_message.send.side_effect = pymsteams.TeamsWebhookException("error")

    mocker.patch(
        "swo_aws_extension.notifications.pymsteams.connectorcard",
        return_value=mocked_message,
    )

    requests_mocker.post(
        mock_oauth_post_url,
        json=None,
        status=401,
    )

    mocker.patch(
        "mpt_extension_sdk.key_vault.base.KeyVault.get_secret",
        return_value=mock_key_vault_secret_value,
    )
    mocker.patch(
        "mpt_extension_sdk.key_vault.base.KeyVault.set_secret",
        side_effect=pymsteams.TeamsWebhookException("error"),
    )
    test_secret = None
    test_secret = refresh_ccp_openid_secret()
    assert test_secret is None
    assert "Error refreshing OpenID secret" in caplog.text


def test_refresh_ccp_openid_token_with_no_token_in_response(
    mocker,
    requests_mocker,
    settings,
    mock_oauth_post_url,
    caplog,
):
    """
    Test the refresh_ccp_openid_token function with a request exception.
    """
    settings.EXTENSION_CONFIG["MSTEAMS_WEBHOOK_URL"] = "https://teams.webhook"
    mocked_message = mocker.MagicMock()
    mocked_message.send.side_effect = pymsteams.TeamsWebhookException("error")

    mocker.patch(
        "swo_aws_extension.notifications.pymsteams.connectorcard",
        return_value=mocked_message,
    )
    requests_mocker.post(
        mock_oauth_post_url,
        json={},
        status=200,
    )

    mocker.patch(
        "mpt_extension_sdk.key_vault.base.KeyVault.get_secret",
        return_value=None,
    )
    mocker.patch(
        "mpt_extension_sdk.key_vault.base.KeyVault.set_secret",
        side_effect=pymsteams.TeamsWebhookException("error"),
    )
    test_secret = None
    test_secret = refresh_ccp_openid_secret()
    assert test_secret is None
    assert ACCESS_TOKEN_NOT_FOUND_IN_RESPONSE in caplog.text


def test_refresh_ccp_openid_token_with_no_set_secret(
    mocker,
    requests_mocker,
    mock_key_vault_secret_value,
    mock_valid_access_token_response,
    mock_oauth_post_url,
    mock_get_secret_response,
    mock_retrieve_secret_url,
):
    """
    Test the refresh_ccp_openid_token function.
    """

    mocked_send_error = mocker.patch("swo_aws_extension.key_vault.ccp.send_error")

    requests_mocker.get(
        mock_retrieve_secret_url,
        json=mock_get_secret_response,
    )
    requests_mocker.post(
        mock_oauth_post_url,
        json=mock_valid_access_token_response,
    )
    mocker.patch(
        "mpt_extension_sdk.key_vault.base.KeyVault.get_secret",
        return_value=mock_key_vault_secret_value,
    )
    mocker.patch(
        "mpt_extension_sdk.key_vault.base.KeyVault.set_secret",
        return_value=None,
    )
    test_secret = refresh_ccp_openid_secret()
    assert test_secret is None
    mocked_send_error.assert_called_once()
