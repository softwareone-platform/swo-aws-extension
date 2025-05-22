from mpt_extension_sdk.flows.pipeline import Pipeline

from swo_aws_extension.aws.config import Config
from swo_aws_extension.constants import SWO_EXTENSION_MANAGEMENT_ROLE
from swo_aws_extension.flows.steps import (
    AddLinkedAccountStep,
    AssignMPA,
    AssignSplitBillingMPA,
    AssignTransferMPAStep,
    AwaitInvitationLinksStep,
    AwaitTerminationServiceRequestStep,
    AwaitTransferRequestTicketWithOrganizationStep,
    CompleteChangeOrderStep,
    CompletePurchaseOrderStep,
    CompleteTerminationOrderStep,
    CreateChangeSubscriptionStep,
    CreateFinOpsEntitlementStep,
    CreateFinOpsMPAEntitlementStep,
    CreateInitialLinkedAccountStep,
    CreateSubscription,
    CreateTerminationServiceRequestStep,
    CreateTransferRequestTicketWithOrganizationStep,
    CreateUpdateKeeperTicketStep,
    DeleteFinOpsEntitlementsStep,
    MPAPreConfiguration,
    SendInvitationLinksStep,
    SetupChangeContext,
    SetupContextPurchaseTransferWithOrganizationStep,
    SetupContextPurchaseTransferWithoutOrganizationStep,
    SetupPurchaseContext,
    SetupTerminateContextStep,
    SynchronizeAgreementSubscriptionsStep,
    ValidatePurchaseTransferWithoutOrganizationStep,
)
from swo_aws_extension.flows.steps.ccp_onboard import CCPOnboard
from swo_aws_extension.flows.steps.register_transfered_mpa_airtable import (
    RegisterTransferredMPAToAirtableStep,
)
from swo_aws_extension.flows.steps.service_crm_steps import CreateOnboardTicketStep

config = Config()


purchase = Pipeline(
    SetupPurchaseContext(config, SWO_EXTENSION_MANAGEMENT_ROLE),
    AssignMPA(config, SWO_EXTENSION_MANAGEMENT_ROLE),
    MPAPreConfiguration(),
    CreateInitialLinkedAccountStep(),
    CreateSubscription(),
    CCPOnboard(config),
    CreateFinOpsMPAEntitlementStep(),
    CreateFinOpsEntitlementStep(),
    CreateUpdateKeeperTicketStep(),
    CreateOnboardTicketStep(),
    CompletePurchaseOrderStep(),
)

purchase_split_billing = Pipeline(
    SetupPurchaseContext(config, SWO_EXTENSION_MANAGEMENT_ROLE),
    AssignSplitBillingMPA(config, SWO_EXTENSION_MANAGEMENT_ROLE),
    CreateInitialLinkedAccountStep(),
    CreateSubscription(),
    CreateFinOpsEntitlementStep(),
    CompletePurchaseOrderStep(),
)

purchase_transfer_with_organization = Pipeline(
    SetupContextPurchaseTransferWithOrganizationStep(config, SWO_EXTENSION_MANAGEMENT_ROLE),
    CreateTransferRequestTicketWithOrganizationStep(),
    AwaitTransferRequestTicketWithOrganizationStep(),
    AssignTransferMPAStep(config, SWO_EXTENSION_MANAGEMENT_ROLE),
    MPAPreConfiguration(),
    RegisterTransferredMPAToAirtableStep(),
    CreateSubscription(),
    CCPOnboard(config),
    CreateFinOpsMPAEntitlementStep(),
    CreateFinOpsEntitlementStep(),
    CreateOnboardTicketStep(),
    CompletePurchaseOrderStep(),
    SynchronizeAgreementSubscriptionsStep(),
)

purchase_transfer_without_organization = Pipeline(
    ValidatePurchaseTransferWithoutOrganizationStep(),
    SetupContextPurchaseTransferWithoutOrganizationStep(config, SWO_EXTENSION_MANAGEMENT_ROLE),
    AssignMPA(config, SWO_EXTENSION_MANAGEMENT_ROLE),
    MPAPreConfiguration(),
    SendInvitationLinksStep(),
    AwaitInvitationLinksStep(),
    CreateSubscription(),
    CCPOnboard(config),
    CreateFinOpsMPAEntitlementStep(),
    CreateFinOpsEntitlementStep(),
    CreateUpdateKeeperTicketStep(),
    CreateOnboardTicketStep(),
    CompletePurchaseOrderStep(),
    SynchronizeAgreementSubscriptionsStep(),
)

change_order = Pipeline(
    SetupChangeContext(config, SWO_EXTENSION_MANAGEMENT_ROLE),
    AddLinkedAccountStep(),
    CreateChangeSubscriptionStep(),
    CreateFinOpsEntitlementStep(),
    CompleteChangeOrderStep(),
    SynchronizeAgreementSubscriptionsStep(),
)

terminate = Pipeline(
    SetupTerminateContextStep(config, SWO_EXTENSION_MANAGEMENT_ROLE),
    CreateTerminationServiceRequestStep(),
    AwaitTerminationServiceRequestStep(),
    DeleteFinOpsEntitlementsStep(),
    CompleteTerminationOrderStep(),
)
