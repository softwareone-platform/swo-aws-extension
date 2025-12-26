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


INVALID_RESPONSIBILITY_TRANSFER_STATUS = (
    ResponsibilityTransferStatus.DECLINED,
    ResponsibilityTransferStatus.CANCELED,
    ResponsibilityTransferStatus.EXPIRED,
)


class AccountTypesEnum(StrEnum):
    """Order Account types enum."""

    NEW_AWS_ENVIRONMENT = "NewAccount"
    EXISTING_AWS_ENVIRONMENT = "ExistingAccount"


class PhasesEnum(StrEnum):
    """Order phases enum."""

    CREATE_ACCOUNT = "createAccount"
    CREATE_BILLING_TRANSFER_INVITATION = "createBillingTransferInvitation"
    CHECK_BILLING_TRANSFER_INVITATION = "checkBillingTransferInvitation"
    ONBOARD_SERVICES = "onboardServices"
    COMPLETE = "complete"


class ParamPhasesEnum(StrEnum):
    """Parameter phases enum."""

    ORDERING = "ordering"
    FULFILLMENT = "fulfillment"


class OrderParametersEnum(StrEnum):
    """Ordering parameters external Ids."""

    ACCOUNT_TYPE = "accountType"
    MASTER_PAYER_ACCOUNT_ID = "masterPayerID"


class FulfillmentParametersEnum(StrEnum):
    """Change parameters external Ids."""

    PHASE = "phase"
    PM_ACCOUNT_ID = "pmAccountId"
    RESPONSIBILITY_TRANSFER_ID = "responsibilityTransferId"


class OrderProcessingTemplateEnum(StrEnum):
    """Order processing template enum."""

    NEW_ACCOUNT = "New Account - processing"
    EXISTING_ACCOUNT = "Existing Account - processing"


class OrderQueryingTemplateEnum(StrEnum):
    """Order querying template enum."""

    TRANSFER_AWAITING_INVITATIONS = "Querying - awaiting invitations acceptance"
    INVALID_ACCOUNT_ID = "Order querying template - invalid Account ID"
