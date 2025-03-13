from swo.mpt.extensions.flows.pipeline import Pipeline

from swo_aws_extension.aws.config import Config
from swo_aws_extension.constants import SWO_EXTENSION_MANAGEMENT_ROLE
from swo_aws_extension.flows.steps import (
    AwaitMPADecommissionServiceRequestTicketCompletionStep,
    CloseAWSAccountStep,
    CompleteOrder,
    CompletePurchaseOrder,
    CreateLinkedAccount,
    CreateMPADecomissionServiceRequestStep,
    CreateSubscription,
    MPAPreConfiguration,
    SetupContext,
    SetupPurchaseContext,
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
    CompleteOrder("purchase_order"),
)

close_account = Pipeline(
    SetupContext(config, SWO_EXTENSION_MANAGEMENT_ROLE),
    CloseAWSAccountStep(),
    CreateMPADecomissionServiceRequestStep(),
    AwaitMPADecommissionServiceRequestTicketCompletionStep(),
    CompleteOrder("purchase_order"),
)
