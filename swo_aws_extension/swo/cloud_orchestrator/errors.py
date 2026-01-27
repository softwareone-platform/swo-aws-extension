"""Cloud Orchestrator client errors."""

from http import HTTPStatus


class CloudOrchestratorError(Exception):
    """Base exception for Cloud Orchestrator client errors."""


class CloudOrchestratorHttpError(CloudOrchestratorError):
    """HTTP error from Cloud Orchestrator API."""

    def __init__(self, status_code: int, response_content: str):
        self.status_code = status_code
        self.response_content = response_content
        super().__init__(f"{self.status_code} - {self.response_content}")


class CloudOrchestratorNotFoundError(CloudOrchestratorHttpError):
    """Resource not found error (404)."""

    def __init__(self, response_content: str):
        super().__init__(HTTPStatus.NOT_FOUND, response_content)
