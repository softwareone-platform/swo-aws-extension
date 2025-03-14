from enum import StrEnum

PARAM_ACCOUNT_EMAIL = "accountEmail"
PARAM_MPA_ACCOUNT_ID = "mpaAccountId"
PARAM_PHASE = "phase"

PRECONFIG_MPA = "Pre-configuration of MPA"
CREATE_ACCOUNT = "Create Account"
TRANSFER_ACCOUNT = "Transfer Account"
TRANSFER_ACCOUNT_ORG = "Transfer account with an organization"
CHECK_INVITATION_LINK = "Check Invitation Link"
CREATE_SUBSCRIPTIONS = "Create Subscriptions"
CCP_ONBOARD = "CCP Onboard"
COMPLETED = "Completed"

SWO_EXTENSION_MANAGEMENT_ROLE = "swo/ext/SWOExtensionManagementRole"

class FulfillmentParameter(StrEnum):
    CRM_TICKET_ID = "crm_ticket_id"

class OrderParameter(StrEnum):
    TERMINATION = "termination"
    ACCOUNT_ID = "accountId"

class TerminationParameterChoices(StrEnum):
    CLOSE_ACCOUNT = "close_account"
    UNLINK_ACCOUNT = "unlink_account"
