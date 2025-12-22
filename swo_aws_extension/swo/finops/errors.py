from http import HTTPStatus


class FinOpsError(Exception):
    """Base exception for FinOps client errors."""


class FinOpsHttpError(FinOpsError):
    """HTTP error from FinOps API."""

    def __init__(self, status_code: int, response_content: str):
        self.status_code = status_code
        self.response_content = response_content
        super().__init__(f"{self.status_code} - {self.response_content}")


class FinOpsNotFoundError(FinOpsHttpError):
    """Resource not found error (404)."""

    def __init__(self, response_content: str):
        super().__init__(HTTPStatus.NOT_FOUND, response_content)
