from http import HTTPStatus

from swo_aws_extension.swo.cco.errors import CcoError, CcoHttpError, CcoNotFoundError


def test_cco_error_str_with_status_code():
    error = CcoError("something failed", status_code=HTTPStatus.BAD_REQUEST)

    result = str(error)

    assert "400" in result
    assert "something failed" in result


def test_cco_error_str_without_status_code():
    error = CcoError("something failed")

    result = str(error)

    assert "something failed" in result
    assert "400" not in result


def test_cco_http_error_sets_status_code():
    error = CcoHttpError(HTTPStatus.INTERNAL_SERVER_ERROR, "server error")

    result = str(error)

    assert error.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert "server error" in result


def test_cco_not_found_error_sets_status_code():
    error = CcoNotFoundError("resource missing")

    result = str(error)

    assert error.status_code == HTTPStatus.NOT_FOUND
    assert "resource missing" in result
