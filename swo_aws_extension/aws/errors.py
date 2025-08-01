import json
import logging
from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

import botocore.exceptions
from requests import HTTPError, JSONDecodeError, RequestException

P = ParamSpec("P")
R = TypeVar("R")

logger = logging.getLogger(__name__)


class AWSError(Exception):
    pass


class AWSHttpError(AWSError):
    def __init__(self, status_code: int, content: str):
        self.status_code = status_code
        self.content = content
        super().__init__(f"{self.status_code} - {self.content}")


class AWSOpenIdError(AWSHttpError):
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


def wrap_http_error(func: Callable[P, R]) -> Callable[P, R]:
    @wraps(func)
    def _wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return func(*args, **kwargs)
        except HTTPError as e:
            logging.exception(f"HTTP error in {func.__name__}: {e}")
            try:
                raise AWSOpenIdError(e.response.status_code, e.response.json()) from e
            except JSONDecodeError:
                raise AWSHttpError(e.response.status_code, e.response.content.decode()) from e
        except RequestException as e:
            logging.exception(f"Unexpected HTTP error in {func.__name__}: {e}")
            raise AWSHttpError(e.response.status_code, e.response.content.decode()) from e

    return _wrapper


def wrap_boto3_error(func: Callable[P, R]) -> Callable[P, R]:
    @wraps(func)
    def _wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return func(*args, **kwargs)
        except AWSError as e:
            raise e
        except botocore.exceptions.ClientError as e:
            raise AWSError(f"AWS Client error: {e}") from e
        except botocore.exceptions.BotoCoreError as e:
            logging.exception(f"Boto3 SDK error in {func.__name__}: {e}")
            raise AWSError(f"Boto3 SDK error: {e}") from e
        except Exception as e:
            logging.exception(f"Unexpected error in {func.__name__}: {e}")
            raise AWSError(f"Unexpected error: {e}") from e

    return _wrapper
