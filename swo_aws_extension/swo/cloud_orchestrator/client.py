"""Cloud Orchestrator API client."""

import logging
from collections.abc import Callable
from http import HTTPStatus
from typing import Any
from urllib.parse import quote, urljoin

import requests

from swo_aws_extension.constants import DeploymentStatusEnum
from swo_aws_extension.swo.cloud_orchestrator.errors import (
    CloudOrchestratorAuthError,
    CloudOrchestratorConnectionError,
    CloudOrchestratorEmptyResponseError,
    CloudOrchestratorHttpError,
    CloudOrchestratorInvalidJsonError,
    CloudOrchestratorNotFoundError,
    CloudOrchestratorUnexpectedResponseError,
)
from swo_aws_extension.swo.openid.client import OpenIDClient
from swo_aws_extension.swo.openid.errors import OpenIDError

logger = logging.getLogger(__name__)

TIMEOUT = 60

DEPLOYMENT_STATUSES = frozenset(status.value for status in DeploymentStatusEnum)

type ResponseCheck = Callable[[dict[str, Any]], str | None]


def _is_non_empty_string(field_value: Any) -> bool:
    return isinstance(field_value, str) and bool(field_value)


def _check_execution_arn(response_body: dict[str, Any]) -> str | None:
    """Return the contract break when `execution_arn` is not a non-empty string."""
    if not _is_non_empty_string(response_body.get("execution_arn")):
        return "response has no 'execution_arn' string"
    return None


def _check_executions(response_body: dict[str, Any]) -> str | None:
    """Return the contract break when `executions` is not a non-empty list of executions.

    Every execution MUST be an object with a non-empty `execution_arn` string.
    """
    executions = response_body.get("executions")
    if not isinstance(executions, list):
        return "response has no 'executions' list"
    if not executions:
        return "response has an empty 'executions' list"
    for index, execution in enumerate(executions):
        if not isinstance(execution, dict) or _check_execution_arn(execution):
            return f"execution {index} has no 'execution_arn' string"
    return None


def _check_deployment_status(response_body: dict[str, Any]) -> str | None:
    """Return the contract break when `status` is not a known deployment status.

    The comparison ignores the case.
    """
    status = response_body.get("status")
    if not isinstance(status, str) or status.lower() not in DEPLOYMENT_STATUSES:
        return f"response has an unknown 'status' {status!r}"
    return None


def _check_bootstrap_role_status(response_body: dict[str, Any]) -> str | None:
    """Return the contract break when `deployed` is not a boolean."""
    if not isinstance(response_body.get("deployed"), bool):
        return "response has no 'deployed' boolean"
    return None


class CloudOrchestratorClient(requests.Session):
    """Client to interact with Cloud Orchestrator API.

    Every public method raises a `CloudOrchestratorError` subclass when the call fails
    or when the response does not match the endpoint contract.
    """

    def __init__(self, config):
        super().__init__()
        self.config = config
        self._openid_client = OpenIDClient(config)
        base_url = self.config.cloud_orchestrator_api_base_url
        self.base_url = base_url if base_url.endswith("/") else f"{base_url}/"

    def request(self, method: str, url: str, *args, **kwargs):
        """Makes HTTP request with authentication."""
        self._refresh_token()
        kwargs.setdefault("timeout", TIMEOUT)
        return super().request(method, self._build_url(url), *args, **kwargs)

    def get_bootstrap_role_status(self, target_account_id: str) -> dict:
        """Gets the bootstrap role deployment status for the target account.

        The response MUST hold a boolean `deployed`.
        """
        return self._call(
            "bootstrap role check",
            "GET",
            f"api/v1/bootstrap-role/check?target_account_id={quote(target_account_id, safe='')}",
            response_check=_check_bootstrap_role_status,
        )

    def onboard_customer(self, onboard_payload: dict[str, Any]) -> dict:
        """Triggers the deployment of the feature version.

        The response MUST hold a non-empty `execution_arn` string.
        """
        return self._call(
            "onboard",
            "POST",
            "api/v1/marketplace/onboard",
            onboard_payload,
            response_check=_check_execution_arn,
        )

    def upgrade_customer(self, upgrade_payload: dict[str, Any]) -> dict:
        """Triggers the upgrade of the onboarded customer.

        The response MUST hold a non-empty `executions` list. Every execution MUST hold
        a non-empty `execution_arn` string.
        """
        return self._call(
            "upgrade",
            "POST",
            "api/v1/marketplace/upgrade",
            upgrade_payload,
            response_check=_check_executions,
        )

    def get_deployment_status(self, execution_arn: str) -> dict:
        """Gets the deployment status for the given execution ARN.

        The response MUST hold a `status` that is a known deployment status, in any case.
        """
        return self._call(
            "deployment status check",
            "GET",
            f"api/v1/deployments/execution-arn/{quote(execution_arn, safe='')}",
            response_check=_check_deployment_status,
        )

    def _call(  # noqa: WPS211
        self,
        operation: str,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        response_check: ResponseCheck,
    ) -> dict:
        """Send the request and return the response body as a dict.

        This method logs the request and the response at INFO level.

        Raises:
            CloudOrchestratorAuthError: When the access token is not available.
            CloudOrchestratorConnectionError: When the request does not complete.
            CloudOrchestratorHttpError: When the response status is not 2xx.
            CloudOrchestratorNotFoundError: When the response status is 404.
            CloudOrchestratorEmptyResponseError: When the response body is empty.
            CloudOrchestratorInvalidJsonError: When the response body is not valid JSON.
            CloudOrchestratorUnexpectedResponseError: When the response body is not
                a JSON object, or when `response_check` returns a contract break.
        """
        url = self._build_url(path)
        request_context = {
            "operation": operation,
            "method": method,
            "endpoint": path,
            "payload": payload,
        }
        logger.info(
            "Cloud Orchestrator %s request: %s %s payload=%s", operation, method, url, payload
        )
        try:
            response = self.request(method, path, json=payload)
        except (OpenIDError, KeyError) as error:
            raise CloudOrchestratorAuthError(
                f"access token not available: {error}", **request_context
            ) from error
        except requests.RequestException as error:
            raise CloudOrchestratorConnectionError(
                f"request not completed: {error}", **request_context
            ) from error
        logger.info(
            "Cloud Orchestrator %s response: status=%s body=%s",
            operation,
            response.status_code,
            response.text,
        )
        request_context.update(status_code=response.status_code, response_body=response.text)
        self._check_status(response, request_context)
        response_body = self._decode_body(response, request_context)
        contract_break = response_check(response_body)
        if contract_break:
            raise CloudOrchestratorUnexpectedResponseError(contract_break, **request_context)
        return response_body

    def _check_status(self, response: requests.Response, request_context: dict[str, Any]) -> None:
        """Raise the HTTP error when the response status is not 2xx."""
        if response.status_code == HTTPStatus.NOT_FOUND:
            raise CloudOrchestratorNotFoundError("resource not found", **request_context)
        if not HTTPStatus.OK <= response.status_code < HTTPStatus.MULTIPLE_CHOICES:
            raise CloudOrchestratorHttpError("error status returned", **request_context)

    def _decode_body(
        self, response: requests.Response, request_context: dict[str, Any]
    ) -> dict[str, Any]:
        """Return the response body as a dict.

        Raises:
            CloudOrchestratorEmptyResponseError: When the response body is empty.
            CloudOrchestratorInvalidJsonError: When the response body is not valid JSON.
            CloudOrchestratorUnexpectedResponseError: When the response body is not
                a JSON object.
        """
        if not response.text.strip():
            raise CloudOrchestratorEmptyResponseError("response body is empty", **request_context)
        try:
            response_body = response.json()
        except ValueError as error:
            raise CloudOrchestratorInvalidJsonError(
                "response body is not valid JSON", **request_context
            ) from error
        if not isinstance(response_body, dict):
            raise CloudOrchestratorUnexpectedResponseError(
                f"response is a JSON {type(response_body).__name__}, not an object",
                **request_context,
            )
        return response_body

    def _build_url(self, path: str) -> str:
        """Return the absolute URL of the path, relative to the base URL."""
        return urljoin(self.base_url, path.removeprefix("/"))

    def _refresh_token(self) -> None:
        """Refreshes the access token using OpenID client."""
        access_token = self._openid_client.fetch_access_token(self.config.aws_openid_scope)
        self.headers.update({
            "User-Agent": "swo-extensions/1.0",
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        })
