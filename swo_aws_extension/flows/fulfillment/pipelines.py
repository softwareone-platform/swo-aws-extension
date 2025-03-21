from swo.mpt.extensions.flows.pipeline import Pipeline

from swo_aws_extension.aws.config import Config
from swo_aws_extension.constants import SWO_EXTENSION_MANAGEMENT_ROLE
from swo_aws_extension.flows.steps import CompleteOrder, CreateSubscription
from swo_aws_extension.flows.steps.create_linked_account import CreateLinkedAccount
from swo_aws_extension.flows.steps.mpa_pre_configuration import MPAPreConfiguration
from swo_aws_extension.flows.steps.setup_context import SetupContext

config = Config()
purchase = Pipeline(
    SetupContext(config, SWO_EXTENSION_MANAGEMENT_ROLE),
    MPAPreConfiguration(),
    CreateLinkedAccount(),
    CreateSubscription(),
    CompleteOrder("purchase_order"),
)

change_order = Pipeline(
    CreateSubscription(),
    CompleteOrder("purchase_order"),
)

terminate = Pipeline(
    CompleteOrder("purchase_order"),
)
