from swo.mpt.extensions.flows.pipeline import Pipeline

from swo_aws_extension.aws.config import Config
from swo_aws_extension.constants import SWO_EXTENSION_MANAGEMENT_ROLE
from swo_aws_extension.flows.steps import (
    AwaitMPADecommissionServiceRequestTicketCompletionStep,
    CompleteOrder,
    CompletePurchaseOrder,
    CreateLinkedAccount,
    CreateMPADecomissionServiceRequestStep,
    CreateSubscription,
    MPAPreConfiguration,
    SetupContext,
    SetupPurchaseContext,
    TerminateAWSAccount,
)

config = Config()
purchase = Pipeline(
    SetupPurchaseContext(config, SWO_EXTENSION_MANAGEMENT_ROLE),
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
    TerminateAWSAccount(),
    CreateMPADecomissionServiceRequestStep(),
    AwaitMPADecommissionServiceRequestTicketCompletionStep(),
    CompleteOrder("purchase_order"),
)
