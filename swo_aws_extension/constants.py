from enum import StrEnum

MPT_DATE_TIME_FORMAT = "%Y-%m-%dT%H:%M:00Z"

SWO_EXTENSION_MANAGEMENT_ROLE = "swo/mpt/SWOExtensionManagementRole"
SWO_EXTENSION_BILLING_ROLE = "swo/mpt/SWOExtensionBillingRole"
CRM_EXTERNAL_EMAIL = "marketplace@softwareone.com"
CRM_EXTERNAL_USERNAME = "mpt@marketplace.com"
CRM_SERVICE_TYPE = "MarketPlaceServiceActivation"
CRM_GLOBAL_EXT_USER_ID = "globalacademicExtUserId"
CRM_REQUESTER = "Supplier.Portal"
CRM_SUB_SERVICE = "Service Activation"

COST_EXPLORER_DATE_FORMAT = "%Y-%m-%d"

AWS_MARKETPLACE = "AWS Marketplace"

ERROR = "Error"
DRAFT = "Draft"
VALIDATED = "Validated"
JOURNAL_PENDING_STATUS = [ERROR, DRAFT, VALIDATED]


class UsageMetricTypeEnum(StrEnum):
    """AWS usage metric."""
    MARKETPLACE = "MARKETPLACE"
    USAGE = "USAGE"
    PROVIDER_DISCOUNT = "PROVIDER_DISCOUNT"
    SUPPORT = "SUPPORT"
    REFUND = "REFUND"
    SAVING_PLANS = "SAVING_PLANS"
    RECURRING = "RECURRING"
    SERVICE_INVOICE_ENTITY = "SERVICE_INVOICE_ENTITY"


class AWSServiceEnum(StrEnum):
    """AWS service type."""
    SAVINGS_PLANS_FOR_AWS_COMPUTE_USAGE = "Savings Plans for AWS Compute usage"
    TAX = "Tax"
    REFUND = "Refund"
    SUPPORT = "Support"


class AWSRecordTypeEnum(StrEnum):
    """AWS."""
    USAGE = "Usage"
    SOLUTION_PROVIDER_PROGRAM_DISCOUNT = "Solution Provider Program Discount"
    SUPPORT = "Support"
    REFUND = "Refund"
    SAVING_PLAN_RECURRING_FEE = "SavingsPlanRecurringFee"
    RECURRING = "Recurring"


EXCLUDE_USAGE_SERVICES = [AWSServiceEnum.SAVINGS_PLANS_FOR_AWS_COMPUTE_USAGE]


class ItemSkusEnum(StrEnum):
    """Item sku type."""
    AWS_USAGE = "AWS Usage"
    AWS_MARKETPLACE = "AWS Marketplace"
    AWS_USAGE_INCENTIVATE = "AWS Usage incentivate"
    AWS_OTHER_SERVICES = "AWS Other services"
    AWS_SUPPORT_ENTERPRISE = "AWS Support Enterprise"
    UPFRONT = "Upfront"
    UPFRONT_INCENTIVATE = "Upfront incentivate"
    AWS_SUPPORT = "AWS Support"
    SAVING_PLANS_RECURRING_FEE = "Saving Plans Recurring Fee"
    SAVING_PLANS_RECURRING_FEE_INCENTIVATE = "Saving Plans Recurring Fee incentivate"


AWS_ITEMS_SKUS = [item.value for item in ItemSkusEnum]


class AccountTypesEnum(StrEnum):
    """AWS extension account parameter choice."""
    NEW_ACCOUNT = "NewAccount"
    EXISTING_ACCOUNT = "ExistingAccount"


class PhasesEnum(StrEnum):
    """AWS extension phase number."""
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
    """AWS extension termination parameter choice."""
    CLOSE_ACCOUNT = "CloseAccount"
    UNLINK_ACCOUNT = "UnlinkAccount"


class SupportTypesEnum(StrEnum):
    """AWS extension support type choice."""
    RESOLD_SUPPORT = "ResoldSupport"
    PARTNER_LED_SUPPORT = "PartnerLedSupport"


class TransferTypesEnum(StrEnum):
    """AWS extension transfer type."""
    TRANSFER_WITHOUT_ORGANIZATION = "TransferWithoutOrganization"
    TRANSFER_WITH_ORGANIZATION = "TransferWithOrganization"
    SPLIT_BILLING = "SplitBilling"


class CCPOnboardStatusEnum(StrEnum):
    """CCP onboard statuses."""
    RUNNING = "Running"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"


CRM_EMPTY_TITLE = "Action Required: AWS empty pool for region {region}"
CRM_EMPTY_SUMMARY = (
    "Dear MCoE Team,<br><br>A notification has been generated on the Marketplace"
    " Platform regarding lack of accounts available (configured for "
    "{type_of_support}) in {seller_country}.<br>We need your help to create "
    "accounts following the process to be able to continue with the customer"
    " onboarding.<br><br>Thank you for your attention. <br><br>Best Regards,"
    "<br>Marketplace Platform Team<br>"
)
CRM_EMPTY_ADDITIONAL_INFO = "Empty AWS account pool"
CRM_NOTIFICATION_TITLE = (
    "Action Required: AWS reduce number or accounts in pool for region {region}"
)
CRM_NOTIFICATION_SUMMARY = (
    "Dear MCoE Team,<br><br>A notification has been generated on the Marketplace Platform "
    "regarding running low on the amount of accounts available (configured for {type_of_support})"
    " in {seller_country}.<br>We need your help to create accounts following the process in this"
    " region to continue with the customer onboarding.<br><br>Thank you for your attention. "
    "<br><br>Best Regards,<br>Marketplace Platform Team<br>"
)
CRM_NOTIFICATION_ADDITIONAL_INFO = "Low AWS account pool"

CRM_TERMINATION_TITLE = "Termination of account(s) linked to MPA {mpa_account}"
CRM_TERMINATION_ADDITIONAL_INFO = "AWS Terminate account"
CRM_TERMINATION_SUMMARY = (
    "Dear MCoE Team,<br><br>A notification has been generated on the Marketplace"
    " Platform for termination of an AWS account.<br><br>MPA: {mpa_account}<br>"
    "Termination type: {termination_type}<br>Order Id: {order_id}<br><br>AWS Account to terminate:"
    " {accounts}. Thank you for your attention. <br><br>Best Regards,"
    "<br>Marketplace Platform Team<br>"
)

CRM_KEEPER_TITLE = (
    "Action Required: Keeper update request for account_id={mpa_account} and SCU={scu}"
)
CRM_KEEPER_ADDITIONAL_INFO = "Update Keeper folder name"
CRM_KEEPER_SUMMARY = (
    "Dear MCoE Team,<br><br>A notification has been generated on the Marketplace Platform "
    "regarding updating the Keeper Shared Credentials folder name with the assigned Buyer "
    "SCU<br><br>MPA: {account_id}<br>Account Name: {account_name}<br>Account Email: "
    "{account_email}<br>PLS Enabled: {pls_enabled}<br><br>SCU: {scu}<br>Buyer Id: {buyer_id}"
    "<br><br>Additional data:<br>Order Id: {order_id}<br><br>Thank you for your attention. <br>"
    "<br>Best Regards,<br>Marketplace Platform Team<br>"
)

CRM_TRANSFER_WITH_ORGANIZATION_TITLE = (
    "Action Required: New AWS Onboarding in Marketplace - Transfer with Organization MPA AWS"
    " Transfer {master_payer_id} {email_address}"
)
CRM_TRANSFER_WITH_ORGANIZATION_ADDITIONAL_INFO = "AWS Transfer account with organization"
CRM_TRANSFER_WITH_ORGANIZATION_SUMMARY = (
    "Dear MCoE Team,<br><br>A notification has been generated on the Marketplace Platform"
    " regarding Transfer request for AWS MPA Account with organization.<br>Details of transfer:"
    " <br>MPA: {master_payer_id}<br>Contact: {email_address}<br>Order Id: {order_id}<br>"
    "<br>Thank you for your attention."
    " <br><br>Best Regards,<br>Marketplace Platform Team<br>"
)

CRM_NEW_ACCOUNT_TITLE = "New AWS Onboarding in Marketplace"
CRM_NEW_ACCOUNT_ADDITIONAL_INFO = "AWS New AWS linked account created"
CRM_NEW_ACCOUNT_SUMMARY = (
    "Dear MCoE Team,<br><br>Good News!! <br>New customer for AWS is being onboarded in Marketplace"
    "<br>Here are some details: <br> Customer: {customer_name}<br> SCU: {buyer_external_id}<br> "
    "Order: {order_id}<br> MasterPayerId: {master_payer_id}<br><br>Thank you for your attention. "
    "<br><br>Best Regards,<br>Marketplace Platform Team<br>"
)

CRM_NEW_ACCOUNT_REQUIRES_ATTENTION_TITLE = "New AWS Onboarding in Marketplace requires attention"
CRM_NEW_ACCOUNT_REQUIRES_ATTENTION_ADDITIONAL_INFO = (
    "AWS New AWS linked account created but onboarding requires attention"
)
CRM_NEW_ACCOUNT_REQUIRES_ATTENTION_SUMMARY = (
    "Dear MCoE Team,<br><br>Good News!! <br>New customer for AWS is being onboarded in Marketplace"
    "<br>Here are some details: <br> Customer: {customer_name}<br> SCU: {buyer_external_id}<br> "
    "Order: {order_id}<br> MasterPayerId: {master_payer_id}. We required your attention "
    "because services onboarding is not been fully finished - ticket reference "
    "{automation_ticket_id}.<br><br>Thank you for your attention. <br><br>Best Regards,"
    "<br>Marketplace Platform Team<br>"
)
CRM_CCP_TICKET_TITLE = "CCP Onboard failed {ccp_engagement_id}"
CRM_CCP_TICKET_ADDITIONAL_INFO = "CCP Onboard failed"
CRM_CCP_TICKET_SUMMARY = (
    "Dear CCP team, please check the status of onboard customer {ccp_engagement_id} within CCP "
    "and CDE as a call error took place that prevented the marketplace automation "
    "to run all scripts. <br>Here are some details:<br><br>"
    "<br>Order Id: {order_id}<br><br>Response: {onboard_status}<br><br>"
    "<br><br>Thanks!"
)


class StateMessageError(StrEnum):
    """State messages."""
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


ACCESS_TOKEN_NOT_FOUND_IN_RESPONSE = "Access token not found in the response"  # noqa: S105
CCP_SECRET_NOT_FOUND_IN_KEY_VAULT = "CCP secret not found in key vault"  # noqa: S105
FAILED_TO_GET_SECRET = "Failed to get secret"  # noqa: S105
FAILED_TO_SAVE_SECRET_TO_KEY_VAULT = "Failed to save secret to key vault"  # noqa: S105


class AwsHandshakeStateEnum(StrEnum):
    """AWS handshake statuses."""
    REQUESTED = "REQUESTED"
    OPEN = "OPEN"
    CANCELED = "CANCELED"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    EXPIRED = "EXPIRED"


class AgreementStatusEnum(StrEnum):
    """MPT Agreement status."""
    ACTIVE = "Active"
    UPDATING = "Updating"


class SubscriptionStatusEnum(StrEnum):
    """MPT subscription status."""
    ACTIVE = "Active"
    CONFIGURING = "Configuring"
    EXPIRED = "Expired"
    TERMINATED = "Terminated"
    UPDATING = "Updating"
    TERMINATING = "Terminating"


class TemplateTypeEnum(StrEnum):
    """MPT template types."""
    ORDER_COMPLETED = "OrderCompleted"
    ORDER_PROCESSING = "OrderProcessing"
    ORDER_QUERYING = "OrderQuerying"


class OrderCompletedTemplateEnum(StrEnum):
    """Order completed templates."""
    TRANSFER_WITH_ORG_WITH_PLS = "Order completed existing tenant with org - pls"
    TRANSFER_WITH_ORG_WITHOUT_PLS = "Order completed existing tenant with org - no pls"
    TRANSFER_WITHOUT_ORG_WITH_PLS = "Order completed existing tenant - pls"
    TRANSFER_WITHOUT_ORG_WITHOUT_PLS = "Order completed existing tenant - no pls"
    NEW_ACCOUNT_WITH_PLS = "Order completed new tenant - pls"
    NEW_ACCOUNT_WITHOUT_PLS = "Order completed new tenant - no pls"
    SPLIT_BILLING = "split agreement - add linked account"
    CHANGE = "New Linked account"
    TERMINATION_TERMINATE = "Termination order - Terminate"
    TERMINATION_DELINK = "Termination order - de-link"


class OrderProcessingTemplateEnum(StrEnum):
    """Order processing templates."""
    NEW_ACCOUNT = "New Tenant - processing"
    CHANGE = "Processing add Linked account"
    TRANSFER_WITH_ORG = "Order processing template transfer with org"
    TRANSFER_WITHOUT_ORG = "Order processing template - invitations sent"
    TRANSFER_WITH_ORG_TICKET_CREATED = "Order processing template transfer"

    TERMINATION = "Processing Termination"
    SPLIT_BILLING = "Split agreement- processing"


class OrderQueryingTemplateEnum(StrEnum):
    """Order querying templates."""
    NEW_ACCOUNT_ROOT_EMAIL_NOT_UNIQUE = "Order querying template - root e-mail provided not unique."
    TRANSFER_AWAITING_INVITATIONS = "Querying - awaiting invitations acceptance"


ORDER_DEFAULT_PROCESSING_TEMPLATE = "Order processing"
COMMAND_INVALID_BILLING_DATE = (
    "Invalid billing date. The billing date must be in the past. "
    "You can't generate the billing of the current month until the 5th."
)
COMMAND_INVALID_BILLING_DATE_FUTURE = "Invalid billing date. Future months are not allowed."

SYNCHRONIZATION_ERROR = "AWS Billing Journal Synchronization Error"
AWS_BILLING_SUCCESS = "AWS Billing Journal Synchronization Success"


class JournalAttachmentFilesNameEnum(StrEnum):
    """Journal attachments file names."""
    RECORD_TYPE_AND_SERVICE_COST = "Record type and service cost"
    SERVICE_INVOICE_ENTITY = "Service invoice entity"
    ORGANIZATION_INVOICES = "Organization invoices"
    MARKETPLACE_USAGE_REPORT = "Marketplace usage report"
