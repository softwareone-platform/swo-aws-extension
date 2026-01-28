"""Cloud Orchestrator API client."""

import logging
from functools import wraps
from http import HTTPStatus
from urllib.parse import urljoin

import requests

from swo_aws_extension.swo.cloud_orchestrator.errors import (
    CloudOrchestratorHttpError,
    CloudOrchestratorNotFoundError,
)
from swo_aws_extension.swo.openid.client import OpenIDClient

logger = logging.getLogger(__name__)

TIMEOUT = 60


def wrap_http_error(func):
    """Decorator to wrap HTTP errors into Cloud Orchestrator errors."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except requests.HTTPError as err:
            if err.response.status_code == HTTPStatus.NOT_FOUND:
                raise CloudOrchestratorNotFoundError(err.response.text) from err
            raise CloudOrchestratorHttpError(err.response.status_code, err.response.text) from err

    return wrapper


class CloudOrchestratorClient(requests.Session):
    """Client to interact with Cloud Orchestrator API."""

    def __init__(self, config):
        super().__init__()
        self.config = config
        self._openid_client = OpenIDClient(config)
        base_url = self.config.cloud_orchestrator_api_base_url
        self.base_url = base_url if base_url.endswith("/") else f"{base_url}/"

    def request(self, method: str, url: str, *args, **kwargs):
        """Makes HTTP request with authentication."""
        self._refresh_token()
        if url and url[0] == "/":
            url = url[1:]
        url = urljoin(self.base_url, url)
        kwargs.setdefault("timeout", TIMEOUT)
        return super().request(method, url, *args, **kwargs)

    @wrap_http_error
    def get_bootstrap_role_status(self, target_account_id: str) -> dict:
        """Gets the bootstrap role deployment status for the target account."""
        response = self.get(
            url=f"api/v1/bootstrap-role/check?target_account_id={target_account_id}"
        )
        response.raise_for_status()

        return response.json()

    def _refresh_token(self) -> None:
        """Refreshes the access token using OpenID client."""
        access_token = self._openid_client.fetch_access_token(self.config.aws_openid_scope)
        self.headers.update({
            "User-Agent": "swo-extensions/1.0",
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        })
