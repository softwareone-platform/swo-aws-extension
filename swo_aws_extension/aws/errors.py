import json
import logging
from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

import botocore.exceptions
from requests import HTTPError, JSONDecodeError, RequestException

Param = ParamSpec("Param")
RetType = TypeVar("RetType")

logger = logging.getLogger(__name__)


class AWSError(Exception):
    """AWS basic error."""


class AWSHttpError(AWSError):
    """AWS http error."""

    def __init__(self, status_code: int, content: str):
        self.status_code = status_code
        self.content = content
        super().__init__(f"{self.status_code} - {self.content}")


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
            message = f"{message}: {', '.join(self.details)}"
        return message


def wrap_http_error(func: Callable[Param, RetType]) -> Callable[Param, RetType]:  # noqa: UP047
    """Wraps http error to internal."""

    @wraps(func)
    def _wrapper(*args: Param.args, **kwargs: Param.kwargs) -> RetType:
        try:
            return func(*args, **kwargs)
        except HTTPError as e:
            logger.exception("HTTP error in %s.", func.__name__)
            try:
                raise AWSOpenIdError(e.response.status_code, e.response.json()) from e
            except JSONDecodeError:
                raise AWSHttpError(e.response.status_code, e.response.content.decode()) from e
        except RequestException as e:
            logger.exception("Unexpected HTTP error in %s.", func.__name__)
            raise AWSHttpError(e.response.status_code, e.response.content.decode()) from e

    return _wrapper


def wrap_boto3_error(func: Callable[Param, RetType]) -> Callable[Param, RetType]:  # noqa: UP047
    """Wraps boto3 error to internal extension errors."""

    @wraps(func)
    def _wrapper(*args: Param.args, **kwargs: Param.kwargs) -> RetType:
        try:
            return func(*args, **kwargs)
        except AWSError as e:
            raise e from e
        except botocore.exceptions.ClientError as e:
            raise AWSError(f"AWS Client error. {e}") from e
        except botocore.exceptions.BotoCoreError as e:
            logger.exception("Boto3 SDK error in %s.", func.__name__)
            raise AWSError(f"Boto3 SDK error: {e}") from e
        except Exception as e:
            logger.exception("Unexpected error in %s.", func.__name__)
            raise AWSError(f"Unexpected error: {e}") from e

    return _wrapper
