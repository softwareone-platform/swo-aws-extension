from enum import StrEnum

MPT_DATE_TIME_FORMAT = "%Y-%m-%dT%H:%M:00Z"

SWO_EXTENSION_MANAGEMENT_ROLE = "swo/mpt/SWOExtensionManagementRole"
AWS_USAGE_SKU = "AWS Usage"
AWS_MARKETPLACE_SKU = "AWS Marketplace"
AWS_USAGE_INCENTIVATE_SKU = "AWS Usage incentivate"
AWS_OTHER_SERVICES_SKU = "AWS Other services"
AWS_SUPPORT_ENTERPRISE_SKU = "AWS Support Enterprise"
AWS_UPFROM_SKU = "Upfront"
AWS_SUPPORT_SKU = "AWS Support"
AWS_SAVING_PLANS_RECURRING_FEE_SKU = "Saving Plans Recurring Fee"
AWS_ITEMS_SKUS = [
    AWS_USAGE_SKU,
    AWS_MARKETPLACE_SKU,
    AWS_USAGE_INCENTIVATE_SKU,
    AWS_OTHER_SERVICES_SKU,
    AWS_SUPPORT_ENTERPRISE_SKU,
    AWS_UPFROM_SKU,
    AWS_SUPPORT_SKU,
    AWS_SAVING_PLANS_RECURRING_FEE_SKU,
]
TAG_AGREEMENT_ID = "agreement_id"


class AccountTypesEnum(StrEnum):
    NEW_ACCOUNT = "NewAccount"
    EXISTING_ACCOUNT = "ExistingAccount"


class PhasesEnum(StrEnum):
    ASSIGN_MPA = "assignMPA"
    PRECONFIGURATION_MPA = "preConfigurationMPA"
    CREATE_ACCOUNT = "createAccount"
    TRANSFER_ACCOUNT = "transferAccount"
    TRANSFER_ACCOUNT_WITH_ORGANIZATION = "transferAccountWithOrganization"
    CHECK_INVITATION_LINK = "checkInvitationLink"
    CREATE_SUBSCRIPTIONS = "createSubscriptions"
    CCP_ONBOARD = "ccpOnboard"
    COMPLETED = "completed"


CRM_TICKET_RESOLVED_STATE = "Resolved"


class TerminationParameterChoices(StrEnum):
    CLOSE_ACCOUNT = "CloseAccount"
    UNLINK_ACCOUNT = "UnlinkAccount"


class SupportTypesEnum(StrEnum):
    RESOLD_SUPPORT = "ResoldSupport"
    PARTNER_LED_SUPPORT = "PartnerLedSupport"


class TransferTypesEnum(StrEnum):
    TRANSFER_WITHOUT_ORGANIZATION = "TransferWithoutOrganization"
    TRANSFER_WITH_ORGANIZATION = "TransferWithOrganization"
    SPLIT_BILLING = "SplitBilling"


class CCPOnboardStatusEnum(StrEnum):
    RUNNING = "Running"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"


EMPTY_SUMMARY = (
    "Dear MCoE Team,<br><br>A notification has been generated on the Marketplace "
    "Platform regarding lack of accounts available for {order.awsRegion} .<br>"
    "We need your help to create accounts following the process in this region to "
    "continue with the customer Onboarding.<br><br>Thank you for your attention. <br>"
    "<br>Best Regards,<br>Marketplace Platform Team<br>"
)
NOTIFICATION_SUMMARY = (
    "Dear MCoE Team,<br><br>A notification has been generated on the Marketplace "
    "Platform regarding running low on the amount of accounts available for "
    "{order.awsRegion}  .<br>We need your help to create accounts following the "
    "process in this region to continue with the customer Onboarding.<br><br>"
    "Thank you for your attention. <br><br>Best Regards,"
    "<br>Marketplace Platform Team<br>"
)


class StateMessageError(StrEnum):
    REQUESTED = "Review the invitation for account {account}."
    OPEN = "Review the invitation for account {account}."
    CANCELED = (
        "The invitation for the account {account} has been canceled. "
        "Please remove it from the list."
    )
    DECLINED = (
        "The invitation for account {account} has been declined by the receiver. "
        "Please remove it from the list or contact support."
    )
    EXPIRED = (
        "The invitation for the account {account} has expired. "
        "Please remove it from the list or contact support."
    )


TRANSFER_ACCOUNT_INVITATION_NOTE = "Softwareone invite for order {context.order_id}."

TRANSFER_ACCOUNT_INVITATION_FOR_GENERIC_STATE = (
    "Log in the AWS Console and review invitations "
    "for the account {account}. "
    "The current invitation"
    " is in state: {state}"
)

EMPTY_TITLE = "Action Required: AWS empty pool for region {region}"
NOTIFICATION_TITLE = "Action Required: AWS reduce number or accounts in pool for region {region}"
ACCESS_TOKEN_NOT_FOUND_IN_RESPONSE = "Access token not found in the response"
CCP_SECRET_NOT_FOUND_IN_KEY_VAULT = "CCP secret not found in key vault"
FAILED_TO_GET_SECRET = "Failed to get secret"
FAILED_TO_SAVE_SECRET_TO_KEY_VAULT = "Failed to save secret to key vault"


class AwsHandshakeStateEnum(StrEnum):
    REQUESTED = "REQUESTED"
    OPEN = "OPEN"
    CANCELED = "CANCELED"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    EXPIRED = "EXPIRED"


class SubscriptionStatusEnum(StrEnum):
    ACTIVE = "Active"
    CONFIGURING = "Configuring"
    EXPIRED = "Expired"
    TERMINATED = "Terminated"
    UPDATING = "Updating"
    TERMINATING = "Terminating"
