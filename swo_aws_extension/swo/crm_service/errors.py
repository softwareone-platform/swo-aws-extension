from http import HTTPStatus


class CRMError(Exception):
    """Base exception for CRM client errors."""

    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.status_code:
            return f"CRMError ({self.status_code}): {self.message}"
        return f"CRMError: {self.message}"


class CRMHttpError(CRMError):
    """HTTP error from CRM API."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message, status_code)


class CRMNotFoundError(CRMError):
    """Resource not found in CRM API."""

    def __init__(self, message: str):
        super().__init__(message, HTTPStatus.NOT_FOUND)
