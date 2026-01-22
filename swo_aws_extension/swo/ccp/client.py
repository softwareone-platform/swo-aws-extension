import logging
from urllib.parse import urljoin

import requests

from swo_aws_extension.constants import FAILED_TO_GET_SECRET
from swo_aws_extension.notifications import TeamsNotificationManager
from swo_aws_extension.swo.key_vault import KeyVaultManager
from swo_aws_extension.swo.openid.client import OpenIDClient

logger = logging.getLogger(__name__)


TIMEOUT = 60  # secs


class CCPClient(requests.Session):
    """A class to interact with the CCP API."""

    _notifications = TeamsNotificationManager()

    def __init__(self, config):
        super().__init__()
        self.config = config
        self._openid_client = OpenIDClient(config)
        self._key_vault_manager = KeyVaultManager(config)
        base_url = self.config.ccp_api_base_url
        self.base_url = base_url if base_url[-1] == "/" else f"{base_url}/"

    def refresh_secret(self):
        """Refreshes the OpenID token using key vault and sdk."""
        token = self._openid_client.fetch_access_token(self.config.ccp_oauth_credentials_scope)
        if not token:
            return None
        logger.info("Access token retrieved")
        secret = self._get_secret_from_api(token)
        if not secret:
            return None
        logger.info("Secret retrieved from API")
        saved_secret = self._key_vault_manager.save_secret(secret)
        if not saved_secret:
            return None
        logger.info("Refreshed secret stored in key vault")
        return saved_secret

    def _get_secret_from_api(self, token):
        """Retrieves the OpenID secret from the CCP API."""
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
            error = f"{FAILED_TO_GET_SECRET}: secret name: {secret_name}."
            logger.error(error)
            self._notifications.send_error(
                title=FAILED_TO_GET_SECRET,
                text=error,
                button=None,
            )
            return None
        return new_client_secret
