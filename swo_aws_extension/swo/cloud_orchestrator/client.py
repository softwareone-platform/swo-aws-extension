"""Cloud Orchestrator API client."""

import logging
from functools import wraps
from http import HTTPStatus
from typing import Any
from urllib.parse import quote, urljoin

import requests

from swo_aws_extension.swo.cloud_orchestrator.errors import (
    CloudOrchestratorHttpError,
    CloudOrchestratorNotFoundError,
)
from swo_aws_extension.swo.openid.client import OpenIDClient

logger = logging.getLogger(__name__)

TIMEOUT = 60


def _build_http_error(response: requests.Response) -> CloudOrchestratorHttpError:
    """Builds the Cloud Orchestrator error for a failed HTTP response.

    A 500 response uses the standard status phrase instead of the response body.

    Args:
        response: The failed HTTP response.

    Returns:
        The Cloud Orchestrator error for the response.
    """
    if response.status_code == HTTPStatus.NOT_FOUND:
        return CloudOrchestratorNotFoundError(response.text)
    if response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR:
        return CloudOrchestratorHttpError(
            response.status_code, HTTPStatus.INTERNAL_SERVER_ERROR.phrase
        )
    return CloudOrchestratorHttpError(response.status_code, response.text)


def wrap_http_error(func):
    """Decorator to wrap HTTP errors into Cloud Orchestrator errors."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except requests.HTTPError as err:
            raise _build_http_error(err.response) from err

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

    @wrap_http_error
    def onboard_customer(self, onboard_payload: dict[str, Any]) -> dict:
        """Triggers the deployment of the feature version."""
        response = self.post(url="api/v1/marketplace/onboard", json=onboard_payload)
        response.raise_for_status()

        return response.json()

    @wrap_http_error
    def upgrade_customer(self, upgrade_payload: dict[str, Any]) -> dict:
        """Triggers the upgrade of the onboarded customer."""
        # Verbose on purpose while the Cloud Orchestrator upgrade API is in development.
        url = urljoin(self.base_url, "api/v1/marketplace/upgrade")
        logger.info(
            "Cloud Orchestrator upgrade request: POST %s payload=%s",
            url,
            upgrade_payload,
        )
        response = self.post(url=url, json=upgrade_payload)
        logger.info(
            "Cloud Orchestrator upgrade response: status=%s body=%s",
            response.status_code,
            response.text,
        )
        response.raise_for_status()

        return response.json()

    @wrap_http_error
    def get_deployment_status(self, execution_arn: str) -> dict:
        """Gets the deployment status for the given execution ARN."""
        response = self.get(url=f"api/v1/deployments/execution-arn/{quote(execution_arn, safe='')}")
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
