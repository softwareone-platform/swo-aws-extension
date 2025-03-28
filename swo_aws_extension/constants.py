from enum import StrEnum

SWO_EXTENSION_MANAGEMENT_ROLE = "swo/mpt/SWOExtensionManagementRole"


class AccountTypesEnum(StrEnum):
    NEW_ACCOUNT = "NewAccount"
    EXISTING_ACCOUNT = "ExistingAccount"


class PhasesEnum(StrEnum):
    PRECONFIGURATION_MPA = "preConfigurationMPA"
    CREATE_ACCOUNT = "createAccount"
    TRANSFER_ACCOUNT = "transferAccount"
    TRANSFER_ACCOUNT_WITH_ORGANIZATION = "transferAccountWithOrganization"
    CHECK_INVITATION_LINK = "checkInvitationLink"
    CREATE_SUBSCRIPTIONS = "createSubscriptions"
    CCP_ONBOARD = "ccpOnboard"
    COMPLETED = "completed"


CRM_TICKET_COMPLETED_STATE = "Completed"


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
