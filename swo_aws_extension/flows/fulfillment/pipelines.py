from mpt_extension_sdk.flows.pipeline import Pipeline

from swo_aws_extension.aws.config import Config
from swo_aws_extension.constants import SWO_EXTENSION_MANAGEMENT_ROLE
from swo_aws_extension.flows.steps import (
    AssignMPA,
    AssignTransferMPAStep,
    AwaitInvitationLinksStep,
    AwaitTerminationServiceRequestStep,
    AwaitTransferRequestTicketWithOrganizationStep,
    CompleteOrder,
    CompletePurchaseOrder,
    CreateLinkedAccount,
    CreateOrganizationSubscriptions,
    CreateSubscription,
    CreateTerminationServiceRequestStep,
    CreateTransferRequestTicketWithOrganizationStep,
    MPAPreConfiguration,
    SendInvitationLinksStep,
    SetupContext,
    SetupContextPurchaseTransferWithOrganizationStep,
    SetupContextPurchaseTransferWithoutOrganizationStep,
    SetupPurchaseContext,
    ValidatePurchaseTransferWithoutOrganizationStep,
)
from swo_aws_extension.flows.steps.ccp_onboard import CCPOnboard

config = Config()


purchase = Pipeline(
    SetupPurchaseContext(config, SWO_EXTENSION_MANAGEMENT_ROLE),
    AssignMPA(config, SWO_EXTENSION_MANAGEMENT_ROLE),
    MPAPreConfiguration(),
    CreateLinkedAccount(),
    CreateSubscription(),
    CCPOnboard(config),
    CompletePurchaseOrder("purchase_order"),
)

purchase_transfer_with_organization = Pipeline(
    SetupContextPurchaseTransferWithOrganizationStep(config, SWO_EXTENSION_MANAGEMENT_ROLE),
    CreateTransferRequestTicketWithOrganizationStep(),
    AwaitTransferRequestTicketWithOrganizationStep(),
    AssignTransferMPAStep(config, SWO_EXTENSION_MANAGEMENT_ROLE),
    CreateSubscription(),
    CompletePurchaseOrder("purchase_order"),
)

purchase_transfer_without_organization = Pipeline(
    ValidatePurchaseTransferWithoutOrganizationStep(),
    SetupContextPurchaseTransferWithoutOrganizationStep(config, SWO_EXTENSION_MANAGEMENT_ROLE),
    AssignMPA(config, SWO_EXTENSION_MANAGEMENT_ROLE),
    MPAPreConfiguration(),
    SendInvitationLinksStep(),
    AwaitInvitationLinksStep(),
    CompletePurchaseOrder("purchase_order"),
    CreateOrganizationSubscriptions(),
)

change_order = Pipeline(
    CreateSubscription(),
    CompleteOrder("purchase_order"),
)

terminate = Pipeline(
    SetupContext(config, SWO_EXTENSION_MANAGEMENT_ROLE),
    CreateTerminationServiceRequestStep(),
    AwaitTerminationServiceRequestStep(),
    CompleteOrder("purchase_order"),
)
