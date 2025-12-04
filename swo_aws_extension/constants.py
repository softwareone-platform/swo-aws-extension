from enum import StrEnum

MPT_DATE_TIME_FORMAT = "%Y-%m-%dT%H:%M:00Z"

ACCESS_TOKEN_NOT_FOUND_IN_RESPONSE = "Access token not found in the response"  # noqa: S105
CCP_SECRET_NOT_FOUND_IN_KEY_VAULT = "CCP secret not found in key vault"  # noqa: S105
FAILED_TO_GET_SECRET = "Failed to get secret"  # noqa: S105
FAILED_TO_SAVE_SECRET_TO_KEY_VAULT = "Failed to save secret to key vault"  # noqa: S105

SWO_EXTENSION_MANAGEMENT_ROLE = "swo/mpt/SWOExtensionManagementRole"


class SubscriptionStatus(StrEnum):
    """MPT subscription status."""

    ACTIVE = "Active"
    CONFIGURING = "Configuring"
    EXPIRED = "Expired"
    TERMINATED = "Terminated"
    UPDATING = "Updating"
    TERMINATING = "Terminating"


class ItemSkus(StrEnum):
    """Item sku type."""

    AWS_USAGE = "AWS Usage"
    AWS_MARKETPLACE = "AWS Marketplace"
    AWS_USAGE_INCENTIVATE = "AWS Usage incentivate"
    AWS_OTHER_SERVICES = "AWS Other services"
    AWS_SUPPORT_ENTERPRISE = "AWS Support Enterprise"
    UPFRONT = "Upfront"
    UPFRONT_INCENTIVATE = "Upfront incentivate"
    AWS_SUPPORT = "AWS Support"
    SAVING_PLANS_RECURRING_FEE = "Saving Plans Recurring Fee"
    SAVING_PLANS_RECURRING_FEE_INCENTIVATE = "Saving Plans Recurring Fee incentivate"


class FulfillmentParameters(StrEnum):
    """Change parameters external Ids."""

    PHASE = "fulfillment"
    ACCOUNT_REQUEST_ID = "accountRequestId"
    ACCOUNT_EMAIL = "accountEmail"
    ACCOUNT_NAME = "accountName"
    CRM_ONBOARD_TICKET_ID = "crmOnboardTicketId"
    CRM_KEEPER_TICKET_ID = "crmKeeperTicketId"
    CRM_CCP_TICKET_ID = "crmCCPTicketId"
    CRM_TRANSFER_ORGANIZATION_TICKET_ID = "crmTransferOrganizationTicketId"
    CCP_ENGAGEMENT_ID = "ccpEngagementId"
    MPA_EMAIL = "mpaEmail"
    RESPONSIBILITY_TRANSFER_ID = "responsibilityTransferId"
    PMA_ACCOUNT_ID = "pmAccountId"


class ResponsibilityTransferStatus(StrEnum):
    """Responsibility transfer statuses."""

    REQUESTED = "REQUESTED"
    DECLINED = "DECLINED"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"
    ACCEPTED = "ACCEPTED"
    WITHDRAWN = "WITHDRAWN"
