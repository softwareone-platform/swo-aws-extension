import regex as re
from swo.mpt.client.errors import ValidationError

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
