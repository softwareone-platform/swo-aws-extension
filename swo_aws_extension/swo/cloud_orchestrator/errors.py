"""Cloud Orchestrator client errors."""

import json
from typing import Any

MESSAGE_RESPONSE_LIMIT = 500
FACTS_RESPONSE_LIMIT = 2000
MISSING_FACT = "-"


def _truncate(text: str, limit: int) -> str:
    """Return the text cut to the limit, with a marker when the text is longer."""
    if len(text) <= limit:
        return text
    kept_text = text[:limit]
    return f"{kept_text}... (truncated)"


class CloudOrchestratorError(Exception):  # noqa: WPS230
    """Base exception for Cloud Orchestrator client errors.

    The error keeps the request and the response, so that the message and the facts
    identify the failed call without the logs.
    """

    def __init__(  # noqa: WPS211
        self,
        reason: str,
        *,
        operation: str,
        method: str,
        endpoint: str,
        payload: dict[str, Any] | None = None,
        status_code: int | None = None,
        response_body: str | None = None,
    ):
        self.reason = reason
        self.operation = operation
        self.method = method
        self.endpoint = endpoint
        self.payload = payload
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(reason)

    def __str__(self) -> str:
        return self.message

    @property
    def title(self) -> str:
        """Short title that names the failed operation."""
        return f"Cloud Orchestrator {self.operation} failed"

    @property
    def message(self) -> str:
        """One-line message with the reason, the request and the response.

        The response is cut to `MESSAGE_RESPONSE_LIMIT` characters.
        """
        details = [f"{self.method} {self.endpoint}"]
        if self.status_code is not None:
            details.append(f"HTTP {self.status_code}")
        if self.response_body:
            details.append(
                f"response: {_truncate(self.response_body, MESSAGE_RESPONSE_LIMIT)}",
            )
        details_text = ", ".join(details)
        return f"{self.title}: {self.reason} ({details_text})"

    @property
    def facts(self) -> dict[str, str]:
        """Request and response as named facts.

        The response is cut to `FACTS_RESPONSE_LIMIT` characters. A missing value is `-`.
        """
        payload_text = (
            MISSING_FACT if self.payload is None else json.dumps(self.payload, default=str)
        )
        status_text = MISSING_FACT if self.status_code is None else str(self.status_code)
        response_text = (
            _truncate(self.response_body, FACTS_RESPONSE_LIMIT)
            if self.response_body
            else MISSING_FACT
        )
        return {
            "Operation": self.operation,
            "Request": f"{self.method} {self.endpoint}",
            "Payload": payload_text,
            "HTTP status": status_text,
            "Response": response_text,
        }


class CloudOrchestratorHttpError(CloudOrchestratorError):
    """Cloud Orchestrator API returned a status that is not 2xx."""

    @property
    def response_content(self) -> str | None:
        """Raw response body."""
        return self.response_body


class CloudOrchestratorNotFoundError(CloudOrchestratorHttpError):
    """Cloud Orchestrator API returned 404."""


class CloudOrchestratorConnectionError(CloudOrchestratorError):
    """The request to Cloud Orchestrator did not complete, for example on a timeout."""


class CloudOrchestratorAuthError(CloudOrchestratorError):
    """The client did not get the access token for Cloud Orchestrator."""


class CloudOrchestratorEmptyResponseError(CloudOrchestratorError):
    """Cloud Orchestrator API returned a 2xx response with an empty body."""


class CloudOrchestratorInvalidJsonError(CloudOrchestratorError):
    """Cloud Orchestrator API returned a 2xx response with a body that is not valid JSON."""


class CloudOrchestratorUnexpectedResponseError(CloudOrchestratorError):
    """Cloud Orchestrator API returned valid JSON that does not match the endpoint contract."""
