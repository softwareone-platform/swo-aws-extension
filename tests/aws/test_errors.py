import botocore.exceptions
import pytest
from requests import HTTPError, JSONDecodeError, RequestException

from swo_aws_extension.aws.errors import (
    AWSError,
    AWSHttpError,
    AWSOpenIdError,
    wrap_boto3_error,
    wrap_http_error,
)


def test_aws_error():
    error = AWSError("Test error")
    assert str(error) == "Test error"


def test_aws_http_error():
    error = AWSHttpError(500, "Internal Server Error")
    assert str(error) == "500 - Internal Server Error"


def test_aws_openid_error():
    payload = {
        "error": "invalid_client",
        "error_description": "XXXYYYZZZ: The provided client secret keys for app [...]",
        "error_codes": [7000222],
        "timestamp": "2025-04-10 13:54:58Z",
        "trace_id": "69f6231f-ceea-474a-8c9e-fb5355124900",
        "correlation_id": "8968464e-aee5-4469-923e-d1960b29f51d",
        "error_uri": "https://login.microsoftonline.com/error?code=7000222",
    }
    error = AWSOpenIdError(401, payload)
    assert str(error) == "invalid_client - XXXYYYZZZ: The provided client secret keys for app [...]"


def test_aws_openid_error_additional_details():
    payload = {
        "error": "invalid_client",
        "error_description": "XXXYYYZZZ: The provided client secret keys for app [...]",
        "error_codes": [7000222],
        "timestamp": "2025-04-10 13:54:58Z",
        "trace_id": "69f6231f-ceea-474a-8c9e-fb5355124900",
        "correlation_id": "8968464e-aee5-4469-923e-d1960b29f51d",
        "error_uri": "https://login.microsoftonline.com/error?code=7000222",
        "additionalDetails": ["Detail1", "Detail2"],
    }
    error = AWSOpenIdError(401, payload)
    assert str(error) == (
        "invalid_client - XXXYYYZZZ: The provided client secret keys for app [...]: "
        "Detail1, Detail2"
    )


def test_wrap_http_error_http_error(mocker):
    func = mocker.Mock()
    func.__name__ = "test_wrap_http_error_http_error"
    func.side_effect = HTTPError(
        response=mocker.Mock(
            status_code=500,
            json=mocker.Mock(side_effect=JSONDecodeError("msg", "doc", 0)),
            content=b"Internal Server Error",
        )
    )

    wrapped_func = wrap_http_error(func)

    with pytest.raises(AWSHttpError) as e:
        wrapped_func()

    assert str(e.value) == "500 - Internal Server Error"


def test_wrap_http_error_request_exception(mocker):
    func = mocker.Mock()
    func.__name__ = "test_wrap_http_error_request_exception"
    func.side_effect = RequestException(
        response=mocker.Mock(status_code=500, content=b"Internal Server Error")
    )

    wrapped_func = wrap_http_error(func)

    with pytest.raises(AWSError) as e:
        wrapped_func()

    assert str(e.value) == "500 - Internal Server Error"


def test_wrap_boto3_error_client_error(mocker):
    func = mocker.Mock()
    func.__name__ = "test_wrap_boto3_error_client_error"
    func.side_effect = botocore.exceptions.ClientError(
        {"Error": {"Code": "TestError", "Message": "Test error"}}, "TestOperation"
    )

    wrapped_func = wrap_boto3_error(func)

    with pytest.raises(AWSError):
        wrapped_func()


def test_wrap_boto3_error_boto_core_error(mocker):
    func = mocker.Mock()
    func.__name__ = "test_wrap_boto3_error_boto_core_error"
    func.side_effect = botocore.exceptions.BotoCoreError()

    wrapped_func = wrap_boto3_error(func)

    with pytest.raises(AWSError) as e:
        wrapped_func()

    assert str(e.value) == "Boto3 SDK error: An unspecified error occurred"


def test_wrap_boto3_error_unexpected_error(mocker):
    func = mocker.Mock()
    func.__name__ = "test_wrap_boto3_error_unexpected_error"
    func.side_effect = Exception("Unexpected error")

    wrapped_func = wrap_boto3_error(func)

    with pytest.raises(AWSError) as e:
        wrapped_func()

    assert "Unexpected error: Unexpected error" in str(e.value)
