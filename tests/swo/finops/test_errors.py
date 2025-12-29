from http import HTTPStatus

import pytest

from swo_aws_extension.swo.finops.errors import (
    FinOpsError,
    FinOpsHttpError,
    FinOpsNotFoundError,
)


def test_finops_error_is_exception():
    result = FinOpsError("Test error message")

    assert isinstance(result, Exception)
    assert str(result) == "Test error message"


def test_http_error_inherits_from_finops_error():
    result = FinOpsHttpError(HTTPStatus.BAD_REQUEST, "Bad request content")

    assert isinstance(result, FinOpsError)
    assert isinstance(result, Exception)


def test_http_error_stores_status_code():
    result = FinOpsHttpError(HTTPStatus.BAD_REQUEST, "Bad request content")

    assert result.status_code == HTTPStatus.BAD_REQUEST


def test_http_error_stores_response_content():
    result = FinOpsHttpError(HTTPStatus.BAD_REQUEST, "Bad request content")

    assert result.response_content == "Bad request content"


def test_http_error_message_format():
    result = FinOpsHttpError(HTTPStatus.INTERNAL_SERVER_ERROR, "Server error")

    assert str(result) == "500 - Server error"


def test_not_found_error_inherits_from_http():
    result = FinOpsNotFoundError("Resource not found")

    assert isinstance(result, FinOpsHttpError)


def test_not_found_error_status():
    result = FinOpsNotFoundError("Resource not found")

    assert result.status_code == HTTPStatus.NOT_FOUND


def test_not_found_error_stores_response():
    result = FinOpsNotFoundError("Resource not found")

    assert result.response_content == "Resource not found"


def test_not_found_error_message_format():
    result = FinOpsNotFoundError("Entitlement not found")

    assert str(result) == "404 - Entitlement not found"


def test_http_error_can_be_raised_and_caught():
    with pytest.raises(FinOpsHttpError):
        raise FinOpsHttpError(HTTPStatus.FORBIDDEN, "Access denied")


def test_not_found_caught_as_http_error():
    with pytest.raises(FinOpsHttpError):
        raise FinOpsNotFoundError("Not found")


def test_not_found_caught_as_finops_error():
    with pytest.raises(FinOpsError):
        raise FinOpsNotFoundError("Not found")
