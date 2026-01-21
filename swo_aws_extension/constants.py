from enum import StrEnum

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

    PURCHASE = "AWS Billing Transfer Order Completed"
    TERMINATION = "AWS Billing Transfer Termination order approved"


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


CRM_NEW_ACCOUNT_TITLE = "New AWS Onboarding in Marketplace"
CRM_NEW_ACCOUNT_ADDITIONAL_INFO = "AWS New AWS linked account created"
CRM_NEW_ACCOUNT_SUMMARY = (
    "Dear MCoE Team,<br><br>"
    "Good News!! New customer for AWS is being onboarded in Marketplace.<br><br>"
    "Please check the order details and get in touch with the sales team and customer "
    "primary contact for the next steps.<br><br>"
    "<b>Order Details:</b><br>"
    "<ul>"
    "<li><b>Customer:</b> {customer_name}</li>"
    "<li><b>Buyer:</b> {buyer_id}</li>"
    "<li><b>SCU:</b> {buyer_external_id}</li>"
    "<li><b>Order:</b> {order_id}</li>"
    "<li><b>New Account Name:</b> {order_account_name}</li>"
    "<li><b>New Account E-mail:</b> {order_account_email}</li>"
    "</ul>"
    "<b>Technical Point of Contact:</b><br>"
    "<ul>"
    "<li><b>Name:</b> {technical_contact_name}</li>"
    "<li><b>Email:</b> {technical_contact_email}</li>"
    "<li><b>Phone:</b> {technical_contact_phone}</li>"
    "</ul>"
    "<b>Support Information:</b><br>"
    "<ul>"
    "<li><b>Support Type:</b> {support_type}</li>"
    "</ul>"
    "<b>Additional Services:</b><br>"
    "<ul>"
    "<li><b>SWO Additional Services:</b> {supplementary_services}</li>"
    "</ul>"
    "Thank you, team, for your attention and taking all necessary steps!<br><br>"
    "Best Regards,<br>"
    "Marketplace Platform Team"
)

CRM_DEPLOY_ROLES_TITLE = "Action Required: Roles not deployed yet"
CRM_DEPLOY_ROLES_ADDITIONAL_INFO = "New customer joining SWO but no service roles deployed"
CRM_DEPLOY_ROLES_SUMMARY = (
    "Dear MCoE Team,<br><br>"
    "Please get in touch with the customer as we have noticed that the required service roles "
    "for AWS essentials have not been deployed yet.<br><br>"
    "<b>Transfer Details:</b><br>"
    "<ul>"
    "<li><b>Customer:</b> {customer_name}</li>"
    "<li><b>Buyer:</b> {buyer_id}</li>"
    "<li><b>SCU:</b> {buyer_external_id}</li>"
    "<li><b>Order:</b> {order_id}</li>"
    "<li><b>MasterPayerId:</b> {master_payer_id}</li>"
    "</ul>"
    "<b>Technical Point of Contact:</b><br>"
    "<ul>"
    "<li><b>Name:</b> {technical_contact_name}</li>"
    "<li><b>Email:</b> {technical_contact_email}</li>"
    "<li><b>Phone:</b> {technical_contact_phone}</li>"
    "</ul>"
    "Thank you for your attention.<br><br>"
    "Best Regards,<br>"
    "Marketplace Platform Team"
)

CRM_ONBOARD_TITLE = "New AWS on-boarding in Marketplace existing AWS customer"
CRM_ONBOARD_ADDITIONAL_INFO = "New customer joining SWO through billing transfer"
CRM_ONBOARD_SUMMARY = (
    "Dear MCoE Team,<br><br>"
    "Good News!! A new customer for AWS is being onboarded in the SWO Marketplace.<br>"
    "Please check the order details and get in touch with the sales team and customer "
    "primary contact for the next steps.<br><br>"
    "<b>Order Details:</b><br>"
    "<ul>"
    "<li><b>Customer:</b> {customer_name}</li>"
    "<li><b>Buyer:</b> {buyer_id}</li>"
    "<li><b>SCU:</b> {buyer_external_id}</li>"
    "<li><b>Order:</b> {order_id}</li>"
    "<li><b>MasterPayerId:</b> {master_payer_id}</li>"
    "</ul>"
    "<b>Technical Point of Contact:</b><br>"
    "<ul>"
    "<li><b>Name:</b> {technical_contact_name}</li>"
    "<li><b>Email:</b> {technical_contact_email}</li>"
    "<li><b>Phone:</b> {technical_contact_phone}</li>"
    "</ul>"
    "<b>Support Information:</b><br>"
    "<ul>"
    "<li><b>Support Type:</b> {support_type}</li>"
    "</ul>"
    "<b>Additional Services:</b><br>"
    "<ul>"
    "<li><b>SWO Additional Services:</b> {supplementary_services}</li>"
    "</ul>"
    "Thank you for your attention.<br><br>"
    "Best Regards,<br>"
    "Marketplace Platform Team"
)


CUSTOMER_ROLES_NOT_DEPLOYED_MESSAGE = (
    "It seems there is an error with the configured SWO access. SWO roles have not "
    "been created yet. The SWO support team will contact you. Please move the order to "
    "'processing' status once the roles are created."
)
