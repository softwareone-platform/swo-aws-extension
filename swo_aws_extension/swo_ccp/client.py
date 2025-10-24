import logging
from urllib.parse import urljoin, urlparse

import requests
from django.conf import settings
from mpt_extension_sdk.key_vault.base import KeyVault
from requests import HTTPError, Session

from swo_aws_extension.constants import (
    ACCESS_TOKEN_NOT_FOUND_IN_RESPONSE,
    CCP_SECRET_NOT_FOUND_IN_KEY_VAULT,
    FAILED_TO_GET_SECRET,
    FAILED_TO_SAVE_SECRET_TO_KEY_VAULT,
)
from swo_aws_extension.notifications import send_error
from swo_aws_extension.openid import get_openid_token

logger = logging.getLogger(__name__)


TIMEOUT = 60  # secs


class CCPClient(Session):
    """A class to interact with the CCP API."""

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.access_token = self.get_ccp_access_token(self.config.ccp_oauth_scope)

        self.headers.update(
            {"User-Agent": "swo-extensions/1.0", "Authorization": f"Bearer {self.access_token}"},
        )
        base_url = self.config.ccp_api_base_url
        self.base_url = f"{base_url}/" if base_url[-1] != "/" else base_url

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
            send_error(
                title=ACCESS_TOKEN_NOT_FOUND_IN_RESPONSE,
                text=error,
                button=None,
            )
            return None
        return access_token

    def request(self, method, url, *args, **kwargs):
        """Prepare request with proper url."""
        url = self._join_url(url)
        return super().request(method, url, *args, **kwargs)

    def prepare_request(self, request, *args, **kwargs):
        """Prepare request with proper url."""
        request.url = self._join_url(request.url)

        return super().prepare_request(request, *args, **kwargs)

    def _join_url(self, url):
        url = url[1:] if url[0] == "/" else url
        return urljoin(self.base_url, url)

    def onboard_customer(self, payload):
        """
        Onboard a customer using the CCP API.

        Args:
            payload: The payload for CCP onboarding.

        Returns:
            The response from the API.
        """
        response = self.post(
            url="/services/aws-essentials/customer?api-version=v2",
            json=payload,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    def _raise_for_status(self, response):
        """
        Raise an HTTPError if the response status code indicates an error.

        Response has always 200 status code, but the body may contain a different status code.
        This method checks the body for the status code and raises an error if it is 404 or 500.
        """
        response.raise_for_status()
        response_data = response.json()
        status_code = response_data.get("statusCode")
        if status_code in {requests.codes.not_found, requests.codes.internal_server_error}:
            http_error_msg = (
                f"{status_code} Client Error: {response_data.get('message')} "
                f"for url: {response.url}"
            )
            raise HTTPError(http_error_msg, response=response)

    def get_onboard_status(self, ccp_engagement_id):
        """
        Get the status of the onboarding process.

        Args:
            ccp_engagement_id: The engagement ID for the onboarding process.

        Returns:
            The response from the API.
        """
        response = self.get(
            url=f"services/aws-essentials/customer/engagement/{ccp_engagement_id}?api-version=v2",
            timeout=TIMEOUT,
        )
        self._raise_for_status(response)
        return response.json()

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

    def _parse_keyvault_name_from_url(self, key_vault_url):
        """
        Parses the key vault URL to extract the name.

        Args.
            key_vault_url: The key vault URL.

        Returns:
            The name of the key vault.
        """
        hostname = urlparse(key_vault_url).hostname or key_vault_url
        return hostname.split(".")[0]

    def get_secret(self, token):
        """
        Retrieves the OpenID secret from the key vault.

        Args:
            token: The access token for the API.

        Returns:
            The secret if successful, None otherwise.
        """
        client_id = self.config.ccp_client_id
        key_vault_url = settings.MPT_KEY_VAULT_NAME
        key_vault_name = self._parse_keyvault_name_from_url(key_vault_url)

        secret_name = self.config.ccp_key_vault_secret_name
        api_url = self.base_url
        api_url = f"{api_url}process/lighthouse/ad/retrieve/secret/{client_id}?api-version=v1"
        api_headers = {"Authorization": f"Bearer {token}"}
        api_response = requests.get(api_url, headers=api_headers, timeout=TIMEOUT)
        api_response.raise_for_status()
        api_response_data = api_response.json()
        new_client_secret = api_response_data.get("clientSecret", None)
        if not new_client_secret:
            error = f"{FAILED_TO_GET_SECRET}: {key_vault_name} and secret name: {secret_name}."
            logger.error(error)
            send_error(
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
            send_error(
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
            error = (
                f"{FAILED_TO_SAVE_SECRET_TO_KEY_VAULT}: {key_vault_name} "
                "and secret name: {config.ccp_key_vault_secret_name}."
            )
            logger.error(error)
            send_error(
                title=FAILED_TO_SAVE_SECRET_TO_KEY_VAULT,
                text=error,
                button=None,
            )
            return None
        logger.info("Access token stored in key vault")
        return saved_secret
