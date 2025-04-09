import logging

import requests
from django.conf import settings
from mpt_extension_sdk.key_vault.base import KeyVault

from swo_aws_extension.aws.config import get_config
from swo_aws_extension.constants import ACCESS_TOKEN_NOT_FOUND_IN_RESPONSE
from swo_aws_extension.notifications import send_error

logger = logging.getLogger(__name__)


def refresh_ccp_openid_secret():
    """
    Refreshes the OpenID token using key vault and sdk.
    """
    config = get_config()
    auth_url = config.ccp_oauth_url
    client_id = config.ccp_client_id
    client_secret = get_ccp_openid_secret()
    key_vault_name = settings.MPT_KEY_VAULT_NAME
    api_url = config.ccp_mpt_api_url
    key_vault = KeyVault(key_vault_name)
    error = ""
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials",
        "scope": config.ccp_scope,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    try:
        response = requests.post(auth_url, headers=headers, data=payload)
        response.raise_for_status()
        response_data = response.json()
        if "access_token" in response_data:
            logger.info("Access token issued")
            access_token = response_data["access_token"]
            api_url = f"https://{api_url}/process/lighthouse/ad/retrieve/secret/{client_id}?api-version=v1"
            api_headers = {"Authorization": f"Bearer {access_token}"}
            api_response = requests.get(api_url, headers=api_headers)
            api_response.raise_for_status()
            api_response_data = api_response.json()
            new_client_secret = api_response_data["clientSecret"]
            saved_secret = key_vault.set_secret(config.ccp_key_vault_secret_name, new_client_secret)
            if not saved_secret:
                error = (
                    f"Failed to save secret to key vault: {key_vault_name} "
                    "and secret name: {config.ccp_key_vault_secret_name}."
                )
                logger.error(error)
                send_error(
                    title="Failed to save secret to key vault",
                    text=error,
                    button=None,
                )
                return None
            logger.info("Access token stored in key vault")
            return saved_secret
        else:
            error = ACCESS_TOKEN_NOT_FOUND_IN_RESPONSE
            send_error(
                title=ACCESS_TOKEN_NOT_FOUND_IN_RESPONSE,
                text=error,
                button=None,
            )
            logger.error(ACCESS_TOKEN_NOT_FOUND_IN_RESPONSE)
            return None
    except requests.exceptions.RequestException as request_err:
        error = f"Error refreshing OpenID secret for {client_id}: {request_err}"
        logger.error(error)
        send_error(
            title="Error refreshing OpenID secret",
            text=error,
            button=None,
        )
        return None


def get_ccp_openid_secret():
    """
    Get the OpenID secret from the key vault.
    """
    config = get_config()
    secret_name = config.ccp_key_vault_secret_name
    key_vault_name = settings.MPT_KEY_VAULT_NAME
    key_vault = KeyVault(key_vault_name)
    secret = key_vault.get_secret(secret_name)
    if not secret:
        error = (
            f"CCP secret not found in key vault: {key_vault_name} and secret name: {secret_name}."
        )
        logging.error(error)
        send_error(
            title="CCP secret not found in key vault",
            text=error,
            button=None,
        )
        secret = None
    return secret
