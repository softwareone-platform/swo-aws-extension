from enum import StrEnum

MPT_DATE_TIME_FORMAT = "%Y-%m-%dT%H:%M:00Z"


ACCESS_TOKEN_NOT_FOUND_IN_RESPONSE = "Access token not found in the response"  # noqa: S105
CCP_SECRET_NOT_FOUND_IN_KEY_VAULT = "CCP secret not found in key vault"  # noqa: S105
FAILED_TO_GET_SECRET = "Failed to get secret"  # noqa: S105
FAILED_TO_SAVE_SECRET_TO_KEY_VAULT = "Failed to save secret to key vault"  # noqa: S105

SWO_EXTENSION_MANAGEMENT_ROLE = "SWOExtensionDevelopmentRole"
CRM_EXTERNAL_EMAIL = "marketplace@softwareone.com"
CRM_EXTERNAL_USERNAME = "mpt@marketplace.com"
CRM_SERVICE_TYPE = "MarketPlaceServiceActivation"
CRM_GLOBAL_EXT_USER_ID = "globalacademicExtUserId"
CRM_REQUESTER = "Supplier.Portal"
CRM_SUB_SERVICE = "Service Activation"


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
    CREATE_SUBSCRIPTION = "createSubscription"
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
    CRM_ONBOARD_TICKET_ID = "crmOnboardTicketId"


class OrderProcessingTemplateEnum(StrEnum):
    """Order processing template enum."""

    NEW_ACCOUNT = "New Account - processing"
    EXISTING_ACCOUNT = "Existing Account - processing"


class OrderQueryingTemplateEnum(StrEnum):
    """Order querying template enum."""

    TRANSFER_AWAITING_INVITATIONS = "Querying - awaiting invitations acceptance"
    INVALID_ACCOUNT_ID = "Order querying template - invalid Account ID"


class OrderCompletedTemplate(StrEnum):
    """Order completion templates."""

    NEW_ACCOUNT = "Order completed new account"
    EXISTING_ACCOUNT = "Order completed existing account"
    TERMINATION_NEW_ACCOUNT = "Order terminated new account"
    TERMINATION_EXISTING_ACCOUNT = "Order terminated existing account"


class MptOrderStatus(StrEnum):
    """MPT order statuses."""

    COMPLETED = "Completed"


class FinOpsStatusEnum(StrEnum):
    """FinOps entitlement status enum."""

    ACTIVE = "Active"
    TERMINATED = "Terminated"


CRM_NEW_ACCOUNT_TITLE = "New AWS Onboarding in Marketplace"
CRM_NEW_ACCOUNT_ADDITIONAL_INFO = "AWS New AWS linked account created"
CRM_NEW_ACCOUNT_SUMMARY = (
    "Dear MCoE Team,<br><br>Good News!! <br>New customer for AWS is being onboarded in Marketplace"
    "<br>Here are some details: <br> Customer: {customer_name}<br> SCU: {buyer_external_id}<br> "
    "Order: {order_id}<br> MasterPayerId: {master_payer_id}<br><br>Thank you for your attention. "
    "<br><br>Best Regards,<br>Marketplace Platform Team<br>"
)
