from mpt_extension_sdk.flows.pipeline import Pipeline

from swo_aws_extension.aws.config import Config
from swo_aws_extension.constants import SWO_EXTENSION_MANAGEMENT_ROLE
from swo_aws_extension.flows.steps import (
    AssignMPA,
    AwaitTerminationServiceRequestStep,
    AwaitTransferRequestTicketWithOrganizationStep,
    CompleteOrder,
    CompletePurchaseOrder,
    CreateLinkedAccount,
    CreateSubscription,
    CreateTerminationServiceRequestStep,
    CreateTransferRequestTicketWithOrganizationStep,
    MPAPreConfiguration,
    SetupContext,
    SetupPurchaseContext,
    ValidateLinkedMPAStep,
)

config = Config()
purchase = Pipeline(
    CreateTransferRequestTicketWithOrganizationStep(),
    AwaitTransferRequestTicketWithOrganizationStep(),
    SetupPurchaseContext(config, SWO_EXTENSION_MANAGEMENT_ROLE),
    ValidateLinkedMPAStep(),
    AssignMPA(config, SWO_EXTENSION_MANAGEMENT_ROLE),
    MPAPreConfiguration(),
    CreateLinkedAccount(),
    CreateSubscription(),
    CompletePurchaseOrder("purchase_order"),
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
