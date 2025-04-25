from enum import StrEnum

MPT_DATE_TIME_FORMAT = "%Y-%m-%dT%H:%M:00Z"

SWO_EXTENSION_MANAGEMENT_ROLE = "swo/mpt/SWOExtensionManagementRole"
AWS_USAGE_SKU = "AWS Usage"
AWS_MARKETPLACE_SKU = "AWS Marketplace"
AWS_USAGE_INCENTIVATE_SKU = "AWS Usage incentivate"
AWS_OTHER_SERVICES_SKU = "AWS Other services"
AWS_SUPPORT_ENTERPRISE_SKU = "AWS Support Enterprise"
AWS_UPFROM_SKU = "Upfront"
AWS_SUPPORT_SKU = "AWS Support"
AWS_SAVING_PLANS_RECURRING_FEE_SKU = "Saving Plans Recurring Fee"
AWS_ITEMS_SKUS = [
    AWS_USAGE_SKU,
    AWS_MARKETPLACE_SKU,
    AWS_USAGE_INCENTIVATE_SKU,
    AWS_OTHER_SERVICES_SKU,
    AWS_SUPPORT_ENTERPRISE_SKU,
    AWS_UPFROM_SKU,
    AWS_SUPPORT_SKU,
    AWS_SAVING_PLANS_RECURRING_FEE_SKU,
]
TAG_AGREEMENT_ID = "agreement_id"
CRM_EXTERNAL_EMAIL = "no-reply@platform.softwareone.com"
CRM_SERVICE_TYPE = "MarketPlaceServiceActivation"
CRM_GLOBAL_EXT_USER_ID = "globalacademicExtUserId"
CRM_REQUESTER = "Supplier.Portal"
CRM_SUB_SERVICE = "Service Activation"


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


class CCPOnboardStatusEnum(StrEnum):
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


ACCESS_TOKEN_NOT_FOUND_IN_RESPONSE = "Access token not found in the response"
CCP_SECRET_NOT_FOUND_IN_KEY_VAULT = "CCP secret not found in key vault"
FAILED_TO_GET_SECRET = "Failed to get secret"
FAILED_TO_SAVE_SECRET_TO_KEY_VAULT = "Failed to save secret to key vault"


class AwsHandshakeStateEnum(StrEnum):
    REQUESTED = "REQUESTED"
    OPEN = "OPEN"
    CANCELED = "CANCELED"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    EXPIRED = "EXPIRED"


class SubscriptionStatusEnum(StrEnum):
    ACTIVE = "Active"
    CONFIGURING = "Configuring"
    EXPIRED = "Expired"
    TERMINATED = "Terminated"
    UPDATING = "Updating"
    TERMINATING = "Terminating"
