from mpt_extension_sdk.flows.pipeline import Pipeline

from swo_aws_extension.aws.config import Config
from swo_aws_extension.constants import SWO_EXTENSION_MANAGEMENT_ROLE
from swo_aws_extension.flows.steps import (
    AddLinkedAccountStep,
    AssignMPA,
    AssignTransferMPAStep,
    AwaitInvitationLinksStep,
    AwaitTerminationServiceRequestStep,
    AwaitTransferRequestTicketWithOrganizationStep,
    CompleteChangeOrderStep,
    CompletePurchaseOrderStep,
    CompleteTerminationOrderStep,
    CreateChangeSubscriptionStep,
    CreateInitialLinkedAccountStep,
    CreateSubscription,
    CreateTerminationServiceRequestStep,
    CreateTransferRequestTicketWithOrganizationStep,
    CreateUpdateKeeperTicketStep,
    MPAPreConfiguration,
    SendInvitationLinksStep,
    SetupAgreementIdInAccountTagsStep,
    SetupChangeContext,
    SetupContext,
    SetupContextPurchaseTransferWithOrganizationStep,
    SetupContextPurchaseTransferWithoutOrganizationStep,
    SetupPurchaseContext,
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
    CreateUpdateKeeperTicketStep(),
    CreateOnboardTicketStep(),
    CompletePurchaseOrderStep(),
)

purchase_transfer_with_organization = Pipeline(
    SetupContextPurchaseTransferWithOrganizationStep(config, SWO_EXTENSION_MANAGEMENT_ROLE),
    CreateTransferRequestTicketWithOrganizationStep(),
    AwaitTransferRequestTicketWithOrganizationStep(),
    AssignTransferMPAStep(config, SWO_EXTENSION_MANAGEMENT_ROLE),
    MPAPreConfiguration(),
    RegisterTransferredMPAToAirtableStep(),
    SetupAgreementIdInAccountTagsStep(),
    CreateSubscription(),
    CCPOnboard(config),
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
    SetupAgreementIdInAccountTagsStep(),
    CreateSubscription(),
    CCPOnboard(config),
    CreateUpdateKeeperTicketStep(),
    CreateOnboardTicketStep(),
    CompletePurchaseOrderStep(),
    SynchronizeAgreementSubscriptionsStep(),
)

change_order = Pipeline(
    SetupChangeContext(config, SWO_EXTENSION_MANAGEMENT_ROLE),
    AddLinkedAccountStep(),
    CreateChangeSubscriptionStep(),
    CompleteChangeOrderStep(),
    SynchronizeAgreementSubscriptionsStep(),
)

terminate = Pipeline(
    SetupContext(config, SWO_EXTENSION_MANAGEMENT_ROLE),
    CreateTerminationServiceRequestStep(),
    AwaitTerminationServiceRequestStep(),
    CompleteTerminationOrderStep(),
)
