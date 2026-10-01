import datetime as dt
import json
import logging
from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from botocore import exceptions as boto_exceptions
from requests import HTTPError, JSONDecodeError, RequestException

FuncParams = ParamSpec("FuncParams")
RetType = TypeVar("RetType")

logger = logging.getLogger(__name__)

# Keys of a boto3 ClientError response already covered by ``str(error)`` or only carrying
# transport metadata. Any other key (for example ``reason`` or ``fieldList`` in Partner
# Central validation errors) is appended to the error message as it explains the failure.
CLIENT_ERROR_RESPONSE_STANDARD_KEYS = frozenset(("Error", "ResponseMetadata"))


class AWSError(Exception):
    """AWS basic error."""


class AWSHttpError(AWSError):
    """AWS http error."""

    def __init__(self, status_code: int, response_content: str):
        self.status_code = status_code
        self.response_content = response_content
        super().__init__(f"{self.status_code} - {self.response_content}")


class AWSOpenIdError(AWSHttpError):
    """AWS openId error."""

    def __init__(self, status_code: int, payload: dict) -> None:
        super().__init__(status_code, json.dumps(payload))
        self.payload: dict = payload
        self.code: str = payload["error"]
        self.message: str = payload["error_description"]
        self.details: list = payload.get("additionalDetails", [])

    def __str__(self) -> str:
        message = f"{self.code} - {self.message}"
        if self.details:
            error_details = ", ".join(self.details)
            message = f"{message}: {error_details}"
        return message


class InvalidDateInTerminateResponsibilityError(AWSError):
    """Raised when date in terminate responsibility is invalid."""

    def __init__(self, message: str, date: dt.datetime) -> None:
        self.message = message
        self.date = date
        super().__init__(message)


def wrap_http_error(func: Callable[FuncParams, RetType]) -> Callable[FuncParams, RetType]:  # noqa: UP047
    """Wraps http error to internal."""

    @wraps(func)
    def _wrapper(*args: FuncParams.args, **kwargs: FuncParams.kwargs) -> RetType:
        try:
            return func(*args, **kwargs)
        except HTTPError as error:
            logger.exception("HTTP error in %s.", func.__name__)
            try:
                raise AWSOpenIdError(error.response.status_code, error.response.json()) from error
            except JSONDecodeError:
                raise AWSHttpError(
                    error.response.status_code, error.response.content.decode()
                ) from error
        except RequestException as error:
            logger.exception("Unexpected HTTP error in %s.", func.__name__)
            raise AWSHttpError(
                error.response.status_code, error.response.content.decode()
            ) from error

    return _wrapper


def format_client_error(error: boto_exceptions.ClientError) -> str:
    """Build the AWSError message of a boto3 ClientError with the service error details."""
    response = error.response or {}
    message = f"AWS Client error. {error}"
    request_id = response.get("ResponseMetadata", {}).get("RequestId")
    if request_id:
        message = f"{message} Request ID: {request_id}."
    details = {
        key: response[key]
        for key in response
        if key not in CLIENT_ERROR_RESPONSE_STANDARD_KEYS
        and response[key] != response.get("Error", {}).get("Message")
    }
    if details:
        message = f"{message} Details: {json.dumps(details, default=str)}"
    return message


def wrap_boto3_error(func: Callable[FuncParams, RetType]) -> Callable[FuncParams, RetType]:  # noqa: UP047
    """Wraps boto3 error to internal extension errors."""

    @wraps(func)
    def _wrapper(*args: FuncParams.args, **kwargs: FuncParams.kwargs) -> RetType:
        try:
            return func(*args, **kwargs)
        except AWSError:
            raise
        except boto_exceptions.ClientError as error:
            raise AWSError(format_client_error(error)) from error
        except boto_exceptions.BotoCoreError as error:
            logger.exception("Boto3 SDK error in %s.", func.__name__)
            raise AWSError(f"Boto3 SDK error: {error}") from error
        except Exception as error:
            logger.exception("Unexpected error in %s.", func.__name__)
            raise AWSError(f"Unexpected error: {error}") from error

    return _wrapper
