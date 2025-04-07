import logging

import requests
from mpt_extension_sdk.key_vault.base import KeyVault

from swo_aws_extension.aws.config import get_config
from swo_aws_extension.notifications import send_error

logger = logging.getLogger(__name__)


def refresh_ccp_openid_token():
    """
    Refreshes the OpenID token using key vault and sdk.
    """
    config = get_config()
    auth_url = config.ccp_oauth_url
    client_id = config.ccp_client_id
    client_secret = config.ccp_client_secret
    key_vault_name = config.mpt_key_vault_name
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
            key_vault.set_secret(config.ccp_key_vault_secret_name, access_token)
            secret = key_vault.get_secret(config.ccp_key_vault_secret_name)
            logger.info("Access token stored in key vault")
            return secret
        else:
            error = "Access token not found in the response"
            send_error(
                title="Access token not found in the response",
                text=error,
                button=None,
            )
            logger.error("Access token not found in the response")
            return None
    except requests.exceptions.RequestException as e:
        error = f"Error refreshing OpenID token for {client_id}: {e}"
        logger.error(error)
        send_error(
            title="Error refreshing OpenID token",
            text=error,
            button=None,
        )
        return None


def get_ccp_openid_token():
    """
    Get the OpenID token from the key vault.
    """
    config = get_config()
    secret_name = config.ccp_key_vault_secret_name
    key_vault_name = config.mpt_key_vault_name
    key_vault = KeyVault(key_vault_name)
    token = key_vault.get_secret(secret_name)
    if not token:
        error = (
            f"CCP token not found in key vault: {key_vault_name} and secret name: {secret_name}."
        )
        logging.error(error)
        send_error(
            title="CCP token not found in key vault",
            text=error,
            button=None,
        )
        token = None
    return token
