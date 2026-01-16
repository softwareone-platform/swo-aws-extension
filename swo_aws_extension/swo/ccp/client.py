import logging
from urllib.parse import urljoin, urlparse

import requests
from django.conf import settings
from mpt_extension_sdk.key_vault.base import KeyVault

from swo_aws_extension.constants import (
    ACCESS_TOKEN_NOT_FOUND_IN_RESPONSE,
    CCP_SECRET_NOT_FOUND_IN_KEY_VAULT,
    FAILED_TO_GET_SECRET,
    FAILED_TO_SAVE_SECRET_TO_KEY_VAULT,
)
from swo_aws_extension.notifications import TeamsNotificationManager
from swo_aws_extension.openid import get_openid_token

logger = logging.getLogger(__name__)


TIMEOUT = 60  # secs


class CCPClient(requests.Session):
    """A class to interact with the CCP API."""

    _notifications = TeamsNotificationManager()

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.access_token = self.get_ccp_access_token(self.config.ccp_oauth_scope)

        self.headers.update(
            {"User-Agent": "swo-extensions/1.0", "Authorization": f"Bearer {self.access_token}"},
        )
        base_url = self.config.ccp_api_base_url
        self.base_url = base_url if base_url[-1] == "/" else f"{base_url}/"

    def get_ccp_access_token(self, scope):
        """Returns CCP access token."""
        client_secret = self.get_secret_from_key_vault()
        if not client_secret:
            return None
        response = get_openid_token(
            endpoint=self.config.ccp_oauth_url,
            client_id=self.config.ccp_client_id,
            client_secret=client_secret,
            scope=scope,
        )
        access_token = response.get("access_token", None)
        if not access_token:
            error = ACCESS_TOKEN_NOT_FOUND_IN_RESPONSE
            logger.error(ACCESS_TOKEN_NOT_FOUND_IN_RESPONSE)
            self._notifications.send_error(
                title=ACCESS_TOKEN_NOT_FOUND_IN_RESPONSE,
                text=error,
                button=None,
            )
            return None
        return access_token

    def refresh_secret(self):
        """
        Refreshes the OpenID token using key vault and sdk.

        Returns:
            The new secret if successful, None otherwise.
        """
        token = self.get_ccp_access_token(self.config.ccp_oauth_credentials_scope)
        if not token:
            return None
        logger.info("Access token retrieved")
        secret = self.get_secret(token)
        if not secret:
            return None
        logger.info("Secret retrieved from key vault")
        saved_secret = self.save_secret_to_key_vault(secret)
        if not saved_secret:
            return None
        logger.info("Refreshed secret stored in key vault")
        return saved_secret

    def get_secret(self, token):
        """
        Retrieves the OpenID secret from the key vault.

        Args:
            token: The access token for the API.

        Returns:
            The secret if successful, None otherwise.
        """
        key_vault_name = self._parse_keyvault_name_from_url(settings.MPT_KEY_VAULT_NAME)
        ccp_client_id = self.config.ccp_client_id
        api_path = f"process/lighthouse/ad/retrieve/secret/{ccp_client_id}?api-version=v1"

        api_response = requests.get(
            urljoin(self.base_url, api_path),
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT,
        )
        api_response.raise_for_status()
        new_client_secret = api_response.json().get("clientSecret", None)
        if not new_client_secret:
            secret_name = self.config.ccp_key_vault_secret_name
            error = f"{FAILED_TO_GET_SECRET}: {key_vault_name} and secret name: {secret_name}."
            logger.error(error)
            self._notifications.send_error(
                title=FAILED_TO_GET_SECRET,
                text=error,
                button=None,
            )
            return None
        return new_client_secret

    def get_secret_from_key_vault(self):
        """
        Retrieves the OpenID secret from the key vault.

        Returns:
            The secret if successful, None otherwise.
        """
        key_vault_name = self._parse_keyvault_name_from_url(settings.MPT_KEY_VAULT_NAME)
        key_vault = KeyVault(key_vault_name)
        secret_name = self.config.ccp_key_vault_secret_name
        secret = key_vault.get_secret(secret_name)
        if not secret:
            error = (
                f"{CCP_SECRET_NOT_FOUND_IN_KEY_VAULT}: "
                f"{key_vault_name} and secret name: {secret_name}."
            )
            logger.error(error)
            self._notifications.send_error(
                title=CCP_SECRET_NOT_FOUND_IN_KEY_VAULT,
                text=error,
                button=None,
            )
            return None
        return secret

    def save_secret_to_key_vault(self, secret):
        """
        Saves the OpenID secret to the key vault.

        Args:
            secret: The secret to save.

        Returns:
            The saved secret if successful, None otherwise.
        """
        key_vault_name = self._parse_keyvault_name_from_url(settings.MPT_KEY_VAULT_NAME)
        key_vault = KeyVault(key_vault_name)
        saved_secret = key_vault.set_secret(self.config.ccp_key_vault_secret_name, secret)
        if not saved_secret:
            secret_name = self.config.ccp_key_vault_secret_name
            error = (
                f"{FAILED_TO_SAVE_SECRET_TO_KEY_VAULT}: {key_vault_name} and "
                f"secret name: {secret_name}."
            )
            logger.error(error)
            self._notifications.send_error(
                title=FAILED_TO_SAVE_SECRET_TO_KEY_VAULT,
                text=error,
                button=None,
            )
            return None
        logger.info("Access token stored in key vault")
        return saved_secret

    def _parse_keyvault_name_from_url(self, key_vault_url):
        """
        Parses the key vault URL to extract the name.

        Args:
            key_vault_url: The key vault URL.

        Returns:
            The name of the key vault.
        """
        hostname = urlparse(key_vault_url).hostname or key_vault_url
        return hostname.split(".")[0]
