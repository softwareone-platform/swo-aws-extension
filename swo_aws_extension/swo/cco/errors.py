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


class SellerExternalIdNotFoundError(Exception):
    """Raised when a seller external ID has no legal entity mapping."""

    def __init__(self, external_id: str):
        self.external_id = external_id
        super().__init__(
            f"No SoftwareOne legal entity mapping found for seller external ID '{external_id}'"
        )
