import json
import logging
from functools import wraps
from typing import Callable, ParamSpec, TypeVar

import botocore.exceptions
from requests import HTTPError, JSONDecodeError, RequestException

Param = ParamSpec("Param")
RetType = TypeVar("RetType")

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


class AWSTerminatingAccountError(AWSError):
    match_code = ""
    match_method = ""
    contains_message = None

    def __init__(self, code, message, method, account_id) -> None:
        """
        Error raised when an account is in the process of being terminated.
        code: The error code. Usually: ConstraintViolationException
        method: The method that was called. Close Account or Unlink Account
        account_id: The ID of the account that is being terminated
        message: The error message
        """
        self.code = code
        self.message = message
        self.method = method
        self.account_id = account_id

    def __str__(self):
        return f"Error terminating account `{self.account_id}` with `{self.method}`: {self.message}"

    @classmethod
    def match(cls, e: botocore.exceptions.ClientError):
        return (
            e.response["Error"]["Code"] == cls.match_code
            and (cls.match_method is None or e.operation_name == cls.match_method)
            and cls.contains_message in e.response["Error"]["Message"]
        )


class AWSTerminationQuotaError(AWSTerminatingAccountError):
    """
    botocore.errorfactory.ConstraintViolationException: An error occurred
    (ConstraintViolationException) when calling the CloseAccount operation:
    You have exceeded close account quota for the past 30 days.
    """

    match_code = "ConstraintViolationException"
    match_method = "CloseAccount"
    contains_message = "You have exceeded close account quota for the past 30 days."


class AWSTerminationCoolOffPeriodError(AWSTerminatingAccountError):
    """
    botocore.errorfactory.ConstraintViolationException: An error occurred
    (ConstraintViolationException) when calling the RemoveAccountFromOrganization operation:
    This operation requires a wait period.  Try again later.

    message: This operation requires a wait period.  Try again later.
    code: ConstraintViolationException
    method: RemoveAccountFromOrganization
    """

    match_code = "ConstraintViolationException"
    match_method = "RemoveAccountFromOrganization"
    contains_message = "Try again later."


class AWSRequerimentsNotMeetError(AWSTerminatingAccountError):
    """
    botocore.errorfactory.ConstraintViolationException: An error occurred
    (ConstraintViolationException) when calling the RemoveAccountFromOrganization operation:
    The member account is missing one or more of the prerequisites required to operate as a
    standalone account. To add what is missing, sign-in to the member account using the AWS
    Organizations console, then select to leave the organization. You will then be prompted to
    enter any missing information.


    message: The member account is missing one or more of the prerequisites required to operate
    as a standalone account. To add what is missing, sign-in to the member account using the
    AWS Organizations console, then select to leave the organization. You will then be prompted
    to enter any missing information.

    code: ConstraintViolationException
    method: RemoveAccountFromOrganization
    """

    match_code = "ConstraintViolationException"
    match_method = "RemoveAccountFromOrganization"
    contains_message = "The member account is missing one or more of the prerequisites"


def wrap_http_error(func: Callable[Param, RetType]) -> Callable[Param, RetType]:
    @wraps(func)
    def _wrapper(*args: Param.args, **kwargs: Param.kwargs) -> RetType:
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


def wrap_boto3_error(func: Callable[Param, RetType]) -> Callable[Param, RetType]:
    @wraps(func)
    def _wrapper(*args: Param.args, **kwargs: Param.kwargs) -> RetType:
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


def transform_terminating_aws_exception(exception: botocore.exceptions.ClientError, account_id=""):
    if AWSTerminationCoolOffPeriodError.match(exception):
        return AWSTerminationCoolOffPeriodError(
            exception.response["Error"]["Code"],
            exception.response["Error"]["Message"],
            exception.operation_name,
            account_id,
        )

    if AWSTerminationQuotaError.match(exception):
        return AWSTerminationQuotaError(
            exception.response["Error"]["Code"],
            exception.response["Error"]["Message"],
            exception.operation_name,
            account_id,
        )

    if AWSRequerimentsNotMeetError.match(exception):
        return AWSRequerimentsNotMeetError(
            exception.response["Error"]["Code"],
            exception.response["Error"]["Message"],
            exception.operation_name,
            account_id,
        )
    return AWSTerminatingAccountError(
        exception.response["Error"]["Code"],
        exception.response["Error"]["Message"],
        exception.operation_name,
        account_id,
    )
