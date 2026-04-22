from http import HTTPStatus

from swo_aws_extension.swo.crm_service.errors import (
    CRMError,
    CRMHttpError,
    CRMNotFoundError,
)


def test_crm_error_is_exception():
    result = CRMError("Test error message")

    assert isinstance(result, Exception)


def test_crm_error_str_without_status():
    result = CRMError("Test error message")

    assert str(result) == "CRMError: Test error message"


def test_crm_error_str_with_status():
    result = CRMError("Test error message", HTTPStatus.BAD_REQUEST)

    assert str(result) == "CRMError (400): Test error message"


def test_crm_error_stores_message():
    result = CRMError("Test error message")

    assert result.message == "Test error message"


def test_crm_error_stores_status_code():
    result = CRMError("Test error message", HTTPStatus.BAD_REQUEST)

    assert result.status_code == HTTPStatus.BAD_REQUEST


def test_http_error_inherits_from_crm_error():
    result = CRMHttpError(HTTPStatus.BAD_REQUEST, "Bad request")

    assert isinstance(result, CRMError)
    assert isinstance(result, Exception)


def test_http_error_stores_status_code():
    result = CRMHttpError(HTTPStatus.BAD_REQUEST, "Bad request")

    assert result.status_code == HTTPStatus.BAD_REQUEST


def test_http_error_stores_message():
    result = CRMHttpError(HTTPStatus.BAD_REQUEST, "Bad request")

    assert result.message == "Bad request"


def test_not_found_error_inherits_from_crm():
    result = CRMNotFoundError("Resource not found")

    assert isinstance(result, CRMError)


def test_not_found_error_has_not_found_status():
    result = CRMNotFoundError("Resource not found")

    assert result.status_code == HTTPStatus.NOT_FOUND


def test_not_found_error_stores_message():
    result = CRMNotFoundError("Resource not found")

    assert result.message == "Resource not found"
