from enum import StrEnum


class FulfillmentParameters(StrEnum):
    """Change parameters external Ids."""

    PHASE = "phase"
    ACCOUNT_REQUEST_ID = "accountRequestId"
    ACCOUNT_EMAIL = "accountEmail"
    ACCOUNT_NAME = "accountName"
    CRM_ONBOARD_TICKET_ID = "crmOnboardTicketId"
    CRM_KEEPER_TICKET_ID = "crmKeeperTicketId"
    CRM_CCP_TICKET_ID = "crmCCPTicketId"
    CRM_TRANSFER_ORGANIZATION_TICKET_ID = "crmTransferOrganizationTicketId"
    CCP_ENGAGEMENT_ID = "ccpEngagementId"
    MPA_EMAIL = "mpaEmail"
