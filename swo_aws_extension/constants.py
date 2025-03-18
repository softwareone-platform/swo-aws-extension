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
