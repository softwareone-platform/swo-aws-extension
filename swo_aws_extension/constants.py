from enum import StrEnum

MPT_DATE_TIME_FORMAT = "%Y-%m-%dT%H:%M:00Z"


ACCESS_TOKEN_NOT_FOUND_IN_RESPONSE = "Access token not found in the response"  # noqa: S105
CCP_SECRET_NOT_FOUND_IN_KEY_VAULT = "CCP secret not found in key vault"  # noqa: S105
FAILED_TO_GET_SECRET = "Failed to get secret"  # noqa: S105
FAILED_TO_SAVE_SECRET_TO_KEY_VAULT = "Failed to save secret to key vault"  # noqa: S105

SWO_EXTENSION_MANAGEMENT_ROLE = "SWOExtensionDevelopmentRole"


class SubscriptionStatus(StrEnum):
    """MPT subscription status."""

    ACTIVE = "Active"
    CONFIGURING = "Configuring"
    EXPIRED = "Expired"
    TERMINATED = "Terminated"
    UPDATING = "Updating"
    TERMINATING = "Terminating"


class ResponsibilityTransferStatus(StrEnum):
    """Responsibility transfer statuses."""

    REQUESTED = "REQUESTED"
    DECLINED = "DECLINED"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"
    ACCEPTED = "ACCEPTED"
    WITHDRAWN = "WITHDRAWN"


class AccountTypesEnum(StrEnum):
    """Order Account types enum."""

    NEW_AWS_ENVIRONMENT = "NewAccount"
    EXISTING_AWS_ENVIRONMENT = "ExistingAccount"


class PhasesEnum(StrEnum):
    """Order phases enum."""

    CREATE_ACCOUNT = "createAccount"
    CREATE_BILLING_TRANSFER_INVITATION = "createBillingTransferInvitation"


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
    RESPONSIBILITY_TRANSFER_ID = "responsibilityTransferId"
