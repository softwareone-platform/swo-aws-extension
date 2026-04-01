from http import HTTPStatus


class CcoError(Exception):
    """Base exception for CCO client errors."""

    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.status_code:
            return f"CcoError ({self.status_code}): {self.message}"
        return f"CcoError: {self.message}"


class CcoHttpError(CcoError):
    """HTTP error from CCO API."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message, status_code)


class CcoNotFoundError(CcoError):
    """Resource not found in CCO API."""

    def __init__(self, message: str):
        super().__init__(message, HTTPStatus.NOT_FOUND)
