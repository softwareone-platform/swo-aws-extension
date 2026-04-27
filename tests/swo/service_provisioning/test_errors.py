from http import HTTPStatus

from swo_aws_extension.swo.service_provisioning.errors import (
    ServiceProvisioningError,
    ServiceProvisioningHttpError,
)


def test_error_str_with_status_code():
    error = ServiceProvisioningError("something failed", status_code=HTTPStatus.BAD_REQUEST)

    result = str(error)

    assert "400" in result
    assert "something failed" in result


def test_error_str_without_status_code():
    error = ServiceProvisioningError("something failed")

    result = str(error)

    assert "something failed" in result
    assert "400" not in result


def test_http_error_sets_status_code():
    error = ServiceProvisioningHttpError(HTTPStatus.INTERNAL_SERVER_ERROR, "server error")

    result = str(error)

    assert error.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert "server error" in result
