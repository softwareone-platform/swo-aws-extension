"""Cloud Orchestrator API client."""

import json
import logging
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

type RequestContext = dict[str, Any]


def _is_non_empty_string(field_value: Any) -> bool:
    return isinstance(field_value, str) and bool(field_value)


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

    def get_bootstrap_role_status(self, target_account_id: str) -> dict[str, Any]:
        """Gets the bootstrap role deployment status for the target account.

        The response MUST hold a boolean `deployed`.

        Raises:
            CloudOrchestratorAuthError: When the access token is not available.
            CloudOrchestratorConnectionError: When the request does not complete.
            CloudOrchestratorNotFoundError: When the response status is 404.
            CloudOrchestratorHttpError: When the response status is not 2xx.
            CloudOrchestratorEmptyResponseError: When the response body is empty.
            CloudOrchestratorInvalidJsonError: When the response body is not valid JSON.
            CloudOrchestratorUnexpectedResponseError: When the response body is not
                a JSON object, or when `deployed` is not a boolean.
        """
        response_body, request_context = self._request_json(
            "bootstrap role check",
            "GET",
            f"api/v1/bootstrap-role/check?target_account_id={quote(target_account_id, safe='')}",
        )
        if not isinstance(response_body.get("deployed"), bool):
            raise CloudOrchestratorUnexpectedResponseError(
                "response has no 'deployed' boolean", **request_context
            )
        return response_body

    def onboard_customer(self, onboard_payload: dict[str, Any]) -> dict[str, Any]:
        """Triggers the deployment of the feature version.

        The response MUST hold a non-empty `execution_arn` string.

        Raises:
            CloudOrchestratorAuthError: When the access token is not available.
            CloudOrchestratorConnectionError: When the request does not complete.
            CloudOrchestratorNotFoundError: When the response status is 404.
            CloudOrchestratorHttpError: When the response status is not 2xx.
            CloudOrchestratorEmptyResponseError: When the response body is empty.
            CloudOrchestratorInvalidJsonError: When the response body is not valid JSON.
            CloudOrchestratorUnexpectedResponseError: When the response body is not
                a JSON object, or when `execution_arn` is not a non-empty string.
        """
        response_body, request_context = self._request_json(
            "onboard", "POST", "api/v1/marketplace/onboard", onboard_payload
        )
        if not _is_non_empty_string(response_body.get("execution_arn")):
            raise CloudOrchestratorUnexpectedResponseError(
                "response has no 'execution_arn' string", **request_context
            )
        return response_body

    def upgrade_customer(self, upgrade_payload: dict[str, Any]) -> dict[str, Any]:
        """Triggers the upgrade of the onboarded customer.

        The response MUST hold a non-empty `executions` list. Every execution MUST be
        an object with a non-empty `execution_arn` string.

        Raises:
            CloudOrchestratorAuthError: When the access token is not available.
            CloudOrchestratorConnectionError: When the request does not complete.
            CloudOrchestratorNotFoundError: When the response status is 404.
            CloudOrchestratorHttpError: When the response status is not 2xx.
            CloudOrchestratorEmptyResponseError: When the response body is empty.
            CloudOrchestratorInvalidJsonError: When the response body is not valid JSON.
            CloudOrchestratorUnexpectedResponseError: When the response body is not
                a JSON object, when `executions` is not a non-empty list, or when
                an execution has no non-empty `execution_arn` string.
        """
        response_body, request_context = self._request_json(
            "upgrade", "POST", "api/v1/marketplace/upgrade", upgrade_payload
        )
        executions = response_body.get("executions")
        if not isinstance(executions, list):
            raise CloudOrchestratorUnexpectedResponseError(
                "response has no 'executions' list", **request_context
            )
        if not executions:
            raise CloudOrchestratorUnexpectedResponseError(
                "response has an empty 'executions' list", **request_context
            )
        for index, execution in enumerate(executions):
            if not isinstance(execution, dict) or not _is_non_empty_string(
                execution.get("execution_arn")
            ):
                raise CloudOrchestratorUnexpectedResponseError(
                    f"execution {index} has no 'execution_arn' string", **request_context
                )
        return response_body

    def get_deployment_status(self, execution_arn: str) -> dict[str, Any]:
        """Gets the deployment status for the given execution ARN.

        The response MUST hold a `status` that is a known deployment status, in any case.

        Raises:
            CloudOrchestratorAuthError: When the access token is not available.
            CloudOrchestratorConnectionError: When the request does not complete.
            CloudOrchestratorNotFoundError: When the response status is 404.
            CloudOrchestratorHttpError: When the response status is not 2xx.
            CloudOrchestratorEmptyResponseError: When the response body is empty.
            CloudOrchestratorInvalidJsonError: When the response body is not valid JSON.
            CloudOrchestratorUnexpectedResponseError: When the response body is not
                a JSON object, or when `status` is not a known deployment status.
        """
        response_body, request_context = self._request_json(
            "deployment status check",
            "GET",
            f"api/v1/deployments/execution-arn/{quote(execution_arn, safe='')}",
        )
        status = response_body.get("status")
        if not isinstance(status, str) or status.lower() not in DeploymentStatusEnum:
            raise CloudOrchestratorUnexpectedResponseError(
                f"response has an unknown 'status' {status!r}", **request_context
            )
        return response_body

    def _request_json(
        self,
        operation: str,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], RequestContext]:
        """Send the request and return the response body as a dict, with the request context.

        The request context holds the request and the response, as the keyword arguments
        of a `CloudOrchestratorError`. This method logs the request and the response at
        INFO level.

        Raises:
            CloudOrchestratorAuthError: When the access token is not available.
            CloudOrchestratorConnectionError: When the request does not complete.
            CloudOrchestratorNotFoundError: When the response status is 404.
            CloudOrchestratorHttpError: When the response status is not 2xx.
            CloudOrchestratorEmptyResponseError: When the response body is empty.
            CloudOrchestratorInvalidJsonError: When the response body is not valid JSON.
            CloudOrchestratorUnexpectedResponseError: When the response body is not
                a JSON object.
        """
        request_context: RequestContext = {
            "operation": operation,
            "method": method,
            "endpoint": path,
            "payload": payload,
        }
        logger.info(
            "Cloud Orchestrator %s request: %s %s payload=%s", operation, method, path, payload
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
        body_text = response.text
        logger.info(
            "Cloud Orchestrator %s response: status=%s body=%s",
            operation,
            response.status_code,
            body_text,
        )
        request_context.update(status_code=response.status_code, response_body=body_text)
        self._check_status(response.status_code, request_context)
        return self._decode_body(body_text, request_context), request_context

    def _check_status(self, status_code: int, request_context: RequestContext) -> None:
        """Raise the HTTP error when the response status is not 2xx."""
        if status_code == HTTPStatus.NOT_FOUND:
            raise CloudOrchestratorNotFoundError("resource not found", **request_context)
        if not HTTPStatus.OK <= status_code < HTTPStatus.MULTIPLE_CHOICES:
            raise CloudOrchestratorHttpError("error status returned", **request_context)

    def _decode_body(self, body_text: str, request_context: RequestContext) -> dict[str, Any]:
        """Return the response body as a dict.

        Raises:
            CloudOrchestratorEmptyResponseError: When the response body is empty.
            CloudOrchestratorInvalidJsonError: When the response body is not valid JSON.
            CloudOrchestratorUnexpectedResponseError: When the response body is not
                a JSON object.
        """
        if not body_text.strip():
            raise CloudOrchestratorEmptyResponseError("response body is empty", **request_context)
        try:
            response_body = json.loads(body_text)
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
