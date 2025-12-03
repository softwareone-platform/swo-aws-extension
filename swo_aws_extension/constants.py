from enum import StrEnum

ACCESS_TOKEN_NOT_FOUND_IN_RESPONSE = "Access token not found in the response"  # noqa: S105
CCP_SECRET_NOT_FOUND_IN_KEY_VAULT = "CCP secret not found in key vault"  # noqa: S105
FAILED_TO_GET_SECRET = "Failed to get secret"  # noqa: S105
FAILED_TO_SAVE_SECRET_TO_KEY_VAULT = "Failed to save secret to key vault"  # noqa: S105

HTTP_STATUS_OK = 200
HTTP_STATUS_NO_CONTENT = 204
HTTP_STATUS_BAD_REQUEST = 400
HTTP_STATUS_UNAUTHORIZED = 401
HTTP_STATUS_NOT_FOUND = 404
HTTP_STATUS_INTERNAL_SERVER_ERROR = 500

SWO_EXTENSION_MANAGEMENT_ROLE = "SWOExtensionDevelopmentRole"


class AccountTypesEnum(StrEnum):
    """Order Account types enum."""

    NEW_AWS_ENVIRONMENT = "NewAccount"
    EXISTING_AWS_ENVIRONMENT = "ExistingAccount"


class PhasesEnum(StrEnum):
    """Order phases enum."""

    ASSIGN_PMA = "assignPMA"
    CREATE_ACCOUNT = "createAccount"


class ParamPhasesEnum(StrEnum):
    """Parameter phases enum."""

    ORDERING = "ordering"
    FULFILLMENT = "fulfillment"


class OrderParametersEnum(StrEnum):
    """Ordering parameters external Ids."""

    ACCOUNT_TYPE = "accountType"


class FulfillmentParametersEnum(StrEnum):
    """Change parameters external Ids."""

    PHASE = "phase"
    PM_ACCOUNT_ID = "pmAccountId"
