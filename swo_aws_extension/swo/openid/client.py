import logging
import time

import requests

from swo_aws_extension.notifications import TeamsNotificationManager
from swo_aws_extension.swo.auth import get_auth_token
from swo_aws_extension.swo.key_vault import KeyVaultManager
from swo_aws_extension.swo.openid.errors import (
    OpenIDHttpError,
    OpenIDSecretNotFoundError,
)

logger = logging.getLogger(__name__)

TOKEN_EXPIRY_BUFFER = 60
DEFAULT_TOKEN_EXPIRY = 3600


class Token:
    """A class representing an OAuth access token with expiry tracking."""

    def __init__(self, access_token: str, expires_in: int | None = None):
        self.access_token = access_token
        self.token_expiry = time.time() + (expires_in or DEFAULT_TOKEN_EXPIRY)

    def is_expired(self) -> bool:
        """Checks if the token is expired or about to expire."""
        return time.time() >= (self.token_expiry - TOKEN_EXPIRY_BUFFER)


class OpenIDClient:
    """A class to interact with OpenID OAuth."""

    _notifications = TeamsNotificationManager()

    def __init__(self, config):
        self.config = config
        self._token: Token | None = None
        self._key_vault_manager = KeyVaultManager(config)

    def fetch_access_token(self, scope):
        """Returns OpenId access token, refreshing if expired."""
        if self._token is None or self._token.is_expired():
            self._token = self._request_new_token(scope)
        return self._token.access_token

    def _request_new_token(self, scope) -> Token:
        """Requests a new access token from the OAuth endpoint."""
        client_secret = self._key_vault_manager.get_secret()
        if not client_secret:
            error_msg = "Client secret not found in key vault"
            logger.error(error_msg)
            self._notifications.send_error(
                title="OpenID Secret Error",
                text=error_msg,
                button=None,
            )
            raise OpenIDSecretNotFoundError(error_msg)

        try:
            response = get_auth_token(
                endpoint=self.config.ccp_oauth_url,
                client_id=self.config.ccp_client_id,
                client_secret=client_secret,
                scope=scope,
            )
        except requests.HTTPError as err:
            response_text = err.response.text
            error_msg = f"HTTP error during token retrieval: {response_text}"
            logger.info(error_msg)
            self._notifications.send_error(
                title="OpenID HTTP Error",
                text=error_msg,
                button=None,
            )
            raise OpenIDHttpError(err.response.status_code, response_text) from err

        return Token(
            access_token=response["access_token"],
            expires_in=response["expires_in"],
        )
