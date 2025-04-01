import regex as re
from mpt_extension_sdk.mpt_http.wrap_http_error import ValidationError

TRACE_ID_REGEX = re.compile(r"(\(00-[0-9a-f]{32}-[0-9a-f]{16}-01\))")


def strip_trace_id(traceback):
    return TRACE_ID_REGEX.sub("(<omitted>)", traceback)


ERR_EMAIL_ALREADY_EXIST = ValidationError(
    "AWS001",
    "Provided email already exists in AWS. Please provide a different email.",
)

ERR_EMAIL_EMPTY = ValidationError(
    "AWS002",
    "Email is empty. Please provide an email.",
)

ERR_ACCOUNT_NAME_EMPTY = ValidationError(
    "AWS003",
    "Account name is empty. Please provide an account name.",
)

ERR_TERMINATION_TYPE_EMPTY = ValidationError(
    "AWS004",
    "Please select correct termination type.",
)

ERR_TERMINATION_AWS = ValidationError(
    "AWS005",
    "The member account `{member_account}` is missing one or more of the prerequisites "
    "required to operate as a standalone account. To add what is missing, sign-in to the member "
    "account using the AWS Organizations console, then select to leave the organization. "
    "You will then be prompted to enter any missing information.",
)
