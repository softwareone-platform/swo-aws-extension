from http import HTTPStatus

from swo_aws_extension.swo.openid.errors import (
    OpenIDError,
    OpenIDHttpError,
    OpenIDSecretNotFoundError,
    OpenIDTokenError,
    OpenIDTokenExpiredError,
)


def test_openid_error_with_status_code():
    error = OpenIDError("Test error", HTTPStatus.BAD_REQUEST)

    result = str(error)

    assert result == "OpenIDError (400): Test error"
    assert error.status_code == HTTPStatus.BAD_REQUEST
    assert error.message == "Test error"


def test_openid_error_without_status_code():
    error = OpenIDError("Test error")

    result = str(error)

    assert result == "OpenIDError: Test error"
    assert error.status_code is None


def test_openid_http_error():
    error = OpenIDHttpError(HTTPStatus.INTERNAL_SERVER_ERROR, "Server error")

    result = str(error)

    assert error.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert error.message == "Server error"
    assert "500" in result


def test_openid_token_error():
    error = OpenIDTokenError("Invalid token")

    result = error

    assert result.status_code == HTTPStatus.UNAUTHORIZED
    assert result.message == "Invalid token"


def test_openid_token_expired_error_default_msg():
    error = OpenIDTokenExpiredError()

    result = error

    assert result.status_code == HTTPStatus.UNAUTHORIZED
    assert result.message == "Access token has expired"


def test_openid_token_expired_error_custom_msg():
    error = OpenIDTokenExpiredError("Custom expired message")

    result = error

    assert result.message == "Custom expired message"


def test_openid_secret_not_found_default_msg():
    error = OpenIDSecretNotFoundError()

    result = error

    assert result.status_code == HTTPStatus.NOT_FOUND
    assert result.message == "Client secret not found in key vault"


def test_openid_secret_not_found_custom_msg():
    error = OpenIDSecretNotFoundError("Custom secret error")

    result = error

    assert result.message == "Custom secret error"
