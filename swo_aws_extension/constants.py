from enum import IntEnum, StrEnum

MPT_DATE_TIME_FORMAT = "%Y-%m-%dT%H:%M:00Z"


ACCESS_TOKEN_NOT_FOUND_IN_RESPONSE = "Access token not found in the response"  # noqa: S105
CCP_SECRET_NOT_FOUND_IN_KEY_VAULT = "CCP secret not found in key vault"  # noqa: S105
FAILED_TO_GET_SECRET = "Failed to get secret"  # noqa: S105
FAILED_TO_SAVE_SECRET_TO_KEY_VAULT = "Failed to save secret to key vault"  # noqa: S105


CRM_EXTERNAL_EMAIL = "marketplace@softwareone.com"
CRM_EXTERNAL_USERNAME = "mpt@marketplace.com"
CRM_SERVICE_TYPE = "MarketPlaceServiceActivation"
CRM_GLOBAL_EXT_USER_ID = "globalacademicExtUserId"
CRM_REQUESTER = "Supplier.Portal"
CRM_SUB_SERVICE = "Service Activation"

BASIC_PRICING_PLAN_ARN = "arn:aws:billingconductor::aws:pricingplan/BasicPricingPlan"

CRM_TICKET_RESOLVED_STATE = "Resolved"
MONTHS_PER_YEAR = 12


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

    CREATE_NEW_AWS_ENVIRONMENT = "createAccount"
    CREATE_BILLING_TRANSFER_INVITATION = "createBillingTransferInvitation"
    CHECK_BILLING_TRANSFER_INVITATION = "checkBillingTransferInvitation"
    CONFIGURE_APN_PROGRAM = "configureApnProgram"
    CREATE_CHANNEL_HANDSHAKE = "createChannelHandshake"
    CHECK_CHANNEL_HANDSHAKE_STATUS = "checkChannelHandshakeStatus"
    CHECK_CUSTOMER_ROLES = "checkCustomerRoles"
    ONBOARD_SERVICES = "onboardServices"
    CHECK_ONBOARD_SERVICES_STATUS = "checkOnboardServicesStatus"
    CREATE_SUBSCRIPTION = "createSubscription"
    COMPLETED = "completed"


class ParamPhasesEnum(StrEnum):
    """Parameter phases enum."""

    ORDERING = "ordering"
    FULFILLMENT = "fulfillment"


class OrderParametersEnum(StrEnum):
    """Ordering parameters external Ids."""

    SUPPORT_TYPE = "supportType"
    ACCOUNT_TYPE = "accountType"
    MASTER_PAYER_ACCOUNT_ID = "masterPayerID"
    CONTACT = "contact"
    ORDER_ACCOUNT_NAME = "orderAccountName"
    ORDER_ACCOUNT_EMAIL = "orderAccountEmail"
    SUPPLEMENTARY_SERVICES = "supplementaryServices"
    NEW_ACCOUNT_INSTRUCTIONS = "newAccountInstructions"
    TECHNICAL_CONTACT_INFO = "technicalContactInfo"
    CONNECT_AWS_BILLING_ACCOUNT = "connectAWSBillingAccount"


class FulfillmentParametersEnum(StrEnum):
    """Change parameters external Ids."""

    PHASE = "phase"
    RESPONSIBILITY_TRANSFER_ID = "responsibilityTransferId"
    CRM_ONBOARD_TICKET_ID = "crmOnboardTicketId"
    CRM_NEW_ACCOUNT_TICKET_ID = "crmNewAccountTicketId"
    CRM_CUSTOMER_ROLE_TICKET_ID = "crmCustomerRoleTicketId"
    CUSTOMER_ROLES_DEPLOYED = "customerRolesDeployed"
    BILLING_GROUP_ARN = "billingGroupArn"
    RELATIONSHIP_ID = "relationshipId"
    CHANNEL_HANDSHAKE_ID = "channelHandshakeId"
    CHANNEL_HANDSHAKE_APPROVED = "channelHandshakeApproved"
    CRM_PLS_TICKET_ID = "crmPLSTicketId"
    CRM_ORDER_FAILED_TICKET_ID = "crmOrderFailedTicketId"
    CRM_TERMINATE_ORDER_TICKET_ID = "crmTerminateOrderTicketId"


class OrderProcessingTemplateEnum(StrEnum):
    """Order processing template enum."""

    NEW_ACCOUNT = "AWS Billing Transfer Order Confirmation and next steps - New AWS account"
    EXISTING_ACCOUNT = (
        "AWS Billing Transfer Order Confirmation and next steps - Existing AWS account"
    )
    TERMINATE = "AWS Billing Transfer Termination order received"


class OrderQueryingTemplateEnum(StrEnum):
    """Order querying template enum."""

    TRANSFER_AWAITING_INVITATIONS = "AWS Billing transfer invitation pending"
    INVALID_ACCOUNT_ID = "Order querying template - invalid Account ID"
    NEW_ACCOUNT_CREATION = "AWS Billing Transfer New AWS account creation"
    WAITING_FOR_CUSTOMER_ROLES = "AWS Billing Transfer Waiting for roles deployment template"
    HANDSHAKE_AWAITING_ACCEPTANCE = "AWS Billing Transfer APN Channel Handshake pending acceptance"


class OrderCompletedTemplate(StrEnum):
    """Order completion templates."""

    PURCHASE = "AWS Billing Transfer - Order Completed"
    TERMINATION = "AWS Billing Transfer Termination order approved"
    TERMINATION_WITHOUT_HANDSHAKE = "AWS Billing Transfer Termination order approved - wt handshake"


class MptOrderStatus(StrEnum):
    """MPT order statuses."""

    COMPLETED = "Completed"


class FinOpsStatusEnum(StrEnum):
    """FinOps entitlement status enum."""

    ACTIVE = "Active"
    TERMINATED = "Terminated"


class CustomerRolesDeployed(StrEnum):
    """Customer roles deployed status."""

    YES = "yes"
    NO_DEPLOYED = "no"


class SupportTypesEnum(StrEnum):
    """Support types enum."""

    PARTNER_LED_SUPPORT = "PartnerLedSupport"
    AWS_RESOLD_SUPPORT = "ResoldSupport"


class ChannelHandshakeStatusEnum(StrEnum):
    """Channel Handshake Status Enum."""

    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"


class ChannelHandshakeDeployed(StrEnum):
    """Channel Handshake deployed status."""

    YES = "yes"
    NO_DEPLOYED = "no"


CUSTOMER_ROLES_NOT_DEPLOYED_MESSAGE = (
    "It seems there is an error with the configured SWO access. SWO roles have not "
    "been created yet. The SWO support team will contact you. Please move the order to "
    "'processing' status once the roles are created."
)

COMMITMENT_ENABLED_ERROR_MESSAGE = (
    "Order failed due to invalid date in terminate responsibility agreement"
    " with reason: The selected withdrawal date doesn't meet the terms of your"
    " partner agreement. Visit AWS Partner Central to view your "
    "partner agreements or contact your AWS Partner for help."
)


class ExpirationPeriodEnum(IntEnum):
    """Expiration period enum."""

    CURRENT_MONTH = 1
    NEXT_MONTH = 2


AWS_ITEMS_SKUS = ("AWS Usage",)
