from enum import StrEnum

MPT_DATE_TIME_FORMAT = "%Y-%m-%dT%H:%M:00Z"


ACCESS_TOKEN_NOT_FOUND_IN_RESPONSE = "Access token not found in the response"  # noqa: S105
CCP_SECRET_NOT_FOUND_IN_KEY_VAULT = "CCP secret not found in key vault"  # noqa: S105
FAILED_TO_GET_SECRET = "Failed to get secret"  # noqa: S105
FAILED_TO_SAVE_SECRET_TO_KEY_VAULT = "Failed to save secret to key vault"  # noqa: S105

SWO_EXTENSION_MANAGEMENT_ROLE = "SWOExtensionDevelopmentRole"
# TODO: Update to the correct role once created
ONBOARD_CUSTOMER_ROLE = "SWOExtensionDevelopmentRole11"

CRM_EXTERNAL_EMAIL = "marketplace@softwareone.com"
CRM_EXTERNAL_USERNAME = "mpt@marketplace.com"
CRM_SERVICE_TYPE = "MarketPlaceServiceActivation"
CRM_GLOBAL_EXT_USER_ID = "globalacademicExtUserId"
CRM_REQUESTER = "Supplier.Portal"
CRM_SUB_SERVICE = "Service Activation"

BASIC_PRICING_PLAN_ARN = "arn:aws:billingconductor::aws:pricingplan/BasicPricingPlan"

CRM_TICKET_RESOLVED_STATE = "Resolved"


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
    CHECK_CUSTOMER_ROLES = "checkCustomerRoles"
    ONBOARD_SERVICES = "onboardServices"
    CREATE_SUBSCRIPTION = "createSubscription"
    COMPLETED = "completed"


class ParamPhasesEnum(StrEnum):
    """Parameter phases enum."""

    ORDERING = "ordering"
    FULFILLMENT = "fulfillment"


class OrderParametersEnum(StrEnum):
    """Ordering parameters external Ids."""

    AWS_TYPE_OF_SUPPORT = "AWSTypeOfSupport"
    SUPPORT_TYPE = "supportType"
    ACCOUNT_TYPE = "accountType"
    MASTER_PAYER_ACCOUNT_ID = "masterPayerID"
    CONTACT = "contact"
    ORDER_ACCOUNT_NAME = "orderAccountName"
    ORDER_ACCOUNT_EMAIL = "orderAccountEmail"


class FulfillmentParametersEnum(StrEnum):
    """Change parameters external Ids."""

    PHASE = "phase"
    PM_ACCOUNT_ID = "pmAccountId"
    RESPONSIBILITY_TRANSFER_ID = "responsibilityTransferId"
    CRM_ONBOARD_TICKET_ID = "crmOnboardTicketId"
    CRM_NEW_ACCOUNT_TICKET_ID = "crmNewAccountTicketId"
    CRM_CUSTOMER_ROLE_TICKET_ID = "crmCustomerRoleTicketId"
    CUSTOMER_ROLES_DEPLOYED = "customerRolesDeployed"


class OrderProcessingTemplateEnum(StrEnum):
    """Order processing template enum."""

    NEW_ACCOUNT = "New Account - processing"
    EXISTING_ACCOUNT = "Existing Account - processing"


class OrderQueryingTemplateEnum(StrEnum):
    """Order querying template enum."""

    TRANSFER_AWAITING_INVITATIONS = "AWS Billing transfer invitation pending"
    INVALID_ACCOUNT_ID = "Order querying template - invalid Account ID"
    NEW_ACCOUNT_CREATION = "AWS Billing Transfer New AWS account creation"
    WAITING_FOR_CUSTOMER_ROLES = "AWS Billing Transfer Waiting for roles deployment template"


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


class CustomerRolesDeployed(StrEnum):
    """Customer roles deployed status."""

    YES = "yes"
    NO_DEPLOYED = "no"


class SupportTypesEnum(StrEnum):
    """Support types enum."""

    PARTNER_LED_SUPPORT = "PartnerLedSupport"
    AWS_RESOLD_SUPPORT = "ResoldSupport"


class AwsTypeOfSupportEnum(StrEnum):
    """AWS type of support enum."""

    ENTERPRISE_SUPPORT = "EnterpriseSupport"
    ENTERPRISE_ON_RAMP = "EnterpriseOnRamp"
    BUSINESS_SUPPORT = "BusinessSupport"
    DEVELOPER_SUPPORT = "DeveloperSupport"
    BASIC_SUPPORT = "BasicSupport"


CRM_NEW_ACCOUNT_TITLE = "New AWS Onboarding in Marketplace"
CRM_NEW_ACCOUNT_ADDITIONAL_INFO = "AWS New AWS linked account created"
CRM_NEW_ACCOUNT_SUMMARY = (
    "Dear MCoE Team,<br><br>Good News!! <br>New customer for AWS is being onboarded in Marketplace"
    "<br>Here are some details: <br> Customer: {customer_name}<br> SCU: {buyer_external_id}<br> "
    "Order: {order_id}<br> New Account name : {order_account_name}<br> New account e-mail : "
    "{order_account_email}<br> Technical point of contact : {technical_contact} <br>"
    "Thank you for your attention. <br><br>Best Regards,<br>Marketplace Platform Team<br>"
)

CRM_DEPLOY_ROLES_TITLE = "Action Required: Roles not deployed yet"
CRM_DEPLOY_ROLES_ADDITIONAL_INFO = "New customer joining SWO but no service roles deployed"
CRM_DEPLOY_ROLES_SUMMARY = (
    "Dear MCoE Team,<br><br>Please get in touch with the customer as we have noticed that the"
    " required service roles for AWS essentials have not been deployed yet. Thank you!"
    "<br>Details of transfer: <br> Customer: {customer_name}<br> SCU: {buyer_external_id}<br>"
    " Order: {order_id}<br> MasterPayerId: {master_payer_id}<br> Technical point of contact :"
    " {technical_contact} <br> Thank you for your attention. <br><br>Best Regards,<br>Marketplace "
    "Platform Team<br>"
)

CRM_ONBOARD_TITLE = "New AWS on-boarding in Marketplace existing AWS customer"
CRM_ONBOARD_ADDITIONAL_INFO = "New customer joining SWO through billing transfer"
CRM_ONBOARD_SUMMARY = (
    "Dear MCoE Team,<br><br>Good News!! <br>A new customer for AWS is being onboarded in the SWO"
    " Marketplace<br>Please check the order details and get in touch with the sales team and "
    "customer primary contact for the next steps.<br>Here are some details: <br> Customer: "
    "{customer_name}<br> SCU: {buyer_external_id}<br> Order: {order_id}<br> MasterPayerId:"
    " {master_payer_id}<br> Technical point of contact : {technical_contact} <br>"
    "Thank you for your attention. <br><br>Best Regards,<br>Marketplace Platform Team<br>"
)

CUSTOMER_ROLES_NOT_DEPLOYED_MESSAGE = (
    "It seems there is an error with the configured SWO access. SWO roles have not "
    "been created yet. The SWO support team will contact you. Please move the order to "
    "'processing' status once the roles are created."
)
