import regex as re
from mpt_extension_sdk.mpt_http.wrap_http_error import ValidationError

from swo_aws_extension.parameters import MAX_ACCOUNT_TRANSFER

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

ERR_TRANSFER_WITH_ORG_MISSING_MPA_ID = ValidationError(
    "AWS006",
    "Account id is empty. Please provide an account id.",
)

ERR_TRANSFER_WITHOUT_ORG_MISSING_ACCOUNT_ID = ValidationError(
    "AWS007",
    "Account id is empty. Please provide an account id.",
)

ERR_INVALID_ACCOUNTS_FORMAT = ValidationError(
    "AWS008",
    "Invalid list of accounts ids. Introduce the 12 digits account numbers "
    "separated by new line.",
)

ERR_TRANSFER_TOO_MANY_ACCOUNTS = ValidationError(
    "AWS009",
    f"Transfer more than {MAX_ACCOUNT_TRANSFER} accounts is not supported. "
    f"Please select the option “Transfer existing AWS account with the organization” to transfer"
    f" all your accounts.",
)

ERR_AWAITING_INVITATION_RESPONSE = ValidationError(
    "AWS010",
    "Awaiting invitation response. For the following accounts: {accounts}. Please accept"
    " the invitation in the AWS console.",
)
