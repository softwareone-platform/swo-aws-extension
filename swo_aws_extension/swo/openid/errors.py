from http import HTTPStatus


class OpenIDError(Exception):
    """Base exception for OpenID client errors."""

    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.status_code:
            return f"OpenIDError ({self.status_code}): {self.message}"
        return f"OpenIDError: {self.message}"


class OpenIDHttpError(OpenIDError):
    """HTTP error from OpenID OAuth."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message, status_code)


class OpenIDTokenError(OpenIDError):
    """Token retrieval or validation error."""

    def __init__(self, message: str):
        super().__init__(message, HTTPStatus.UNAUTHORIZED)


class OpenIDTokenExpiredError(OpenIDError):
    """Token has expired."""

    def __init__(self, message: str = "Access token has expired"):
        super().__init__(message, HTTPStatus.UNAUTHORIZED)


class OpenIDSecretNotFoundError(OpenIDError):
    """Secret not found in key vault."""

    def __init__(self, message: str = "Client secret not found in key vault"):
        super().__init__(message, HTTPStatus.NOT_FOUND)
