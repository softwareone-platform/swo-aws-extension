from enum import StrEnum

SWO_EXTENSION_MANAGEMENT_ROLE = "swo/mpt/SWOExtensionManagementRole"


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
EMPTY_TITLE = "Action Required: AWS empty pool for region {region}"
NOTIFICATION_TITLE = "Action Required: AWS reduce number or accounts in pool for region {region}"
