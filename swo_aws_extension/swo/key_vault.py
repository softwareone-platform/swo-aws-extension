import logging
from urllib.parse import urlparse

from django.conf import settings
from mpt_extension_sdk.key_vault.base import KeyVault

from swo_aws_extension.constants import (
    CCP_SECRET_NOT_FOUND_IN_KEY_VAULT,
    FAILED_TO_SAVE_SECRET_TO_KEY_VAULT,
)
from swo_aws_extension.notifications import TeamsNotificationManager

logger = logging.getLogger(__name__)


class KeyVaultManager:
    """A class to manage Key Vault operations for OpenID OAuth."""

    _notifications = TeamsNotificationManager()

    def __init__(self, config):
        self.config = config
        key_vault_name = self._parse_keyvault_name_from_url(settings.MPT_KEY_VAULT_NAME)
        self._key_vault = KeyVault(key_vault_name)

    def get_secret(self):
        """Retrieves the OpenID secret from the key vault."""
        secret_name = self.config.ccp_key_vault_secret_name
        secret = self._key_vault.get_secret(secret_name)
        if not secret:
            key_vault_name = self._key_vault.key_vault_name
            error = (
                f"{CCP_SECRET_NOT_FOUND_IN_KEY_VAULT}: {key_vault_name} and "
                f"secret name: {secret_name}."
            )
            logger.error(error)
            self._notifications.send_error(
                title=CCP_SECRET_NOT_FOUND_IN_KEY_VAULT,
                text=error,
                button=None,
            )
            return None
        return secret

    def save_secret(self, secret):
        """Saves the OpenID secret to the key vault."""
        saved_secret = self._key_vault.set_secret(self.config.ccp_key_vault_secret_name, secret)
        if not saved_secret:
            secret_name = self.config.ccp_key_vault_secret_name
            key_vault_name = self._key_vault.key_vault_name
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
        """Parses the key vault URL to extract the name."""
        hostname = urlparse(key_vault_url).hostname or key_vault_url
        return hostname.split(".")[0]
