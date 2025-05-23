import json

import pytest
from requests import HTTPError, JSONDecodeError

from mpt_extension_sdk.mpt_http.wrap_http_error import (
    MPTAPIError,
    MPTError,
    wrap_mpt_http_error,
)


def test_simple_error(mpt_error_factory):
    """
    Test the MPTError.
    """
    error_data = mpt_error_factory(500, "Internal Server Error", "Oops!")
    error = MPTAPIError(500, error_data)
    assert error.status_code == 500
    assert error.status == 500
    assert error.title == "Internal Server Error"
    assert error.detail == "Oops!"
    assert error.trace_id == error_data["traceId"]
    assert str(error) == f"500 Internal Server Error - Oops! ({error.trace_id})"
    assert repr(error) == str(error_data)


def test_detailed_error(mpt_error_factory):
    error_data = mpt_error_factory(
        400,
        "Bad Request",
        "One or more validation errors occurred.",
        trace_id="trace-id",
        errors={"id": ["The value of 'id' does not match expected format."]},
    )
    error = MPTAPIError(400, error_data)
    assert error.trace_id == "trace-id"
    assert error.errors == error_data["errors"]
    assert str(error) == (
        "400 Bad Request - One or more validation errors occurred. (trace-id)"
        f"\n{json.dumps(error_data['errors'], indent=2)}"
    )


def test_wrap_http_error(mocker, mpt_error_factory):
    error_data = mpt_error_factory(
        400,
        "Bad Request",
        "One or more validation errors occurred.",
        trace_id="trace-id",
        errors={"id": ["The value of 'id' does not match expected format."]},
    )

    def func():
        response = mocker.MagicMock()
        response.status_code = 400
        response.json.return_value = error_data
        raise HTTPError(response=response)

    wrapped_func = wrap_mpt_http_error(func)

    with pytest.raises(MPTAPIError) as cv:
        wrapped_func()

    assert cv.value.trace_id == "trace-id"
    assert cv.value.errors == error_data["errors"]
    assert str(cv.value) == (
        "400 Bad Request - One or more validation errors occurred. (trace-id)"
        f"\n{json.dumps(error_data['errors'], indent=2)}"
    )


def test_wrap_http_error_json_decode_error(mocker):
    def func():
        response = mocker.MagicMock()
        response.status_code = 500
        response.content = b"Internal Server Error"
        response.json.side_effect = JSONDecodeError("msg", "doc", 0)
        raise HTTPError(response=response)

    wrapped_func = wrap_mpt_http_error(func)

    with pytest.raises(MPTError) as cv:
        wrapped_func()

    assert str(cv.value) == "500 - Internal Server Error"
