from swo.mpt.extensions.flows.pipeline import Pipeline

from swo_aws_extension.aws.config import Config
from swo_aws_extension.constants import SWO_EXTENSION_MANAGEMENT_ROLE
from swo_aws_extension.flows.steps import CompleteOrder, CreateSubscription
from swo_aws_extension.flows.steps.get_mpa_credentials import GetMPACredentials
from swo_aws_extension.flows.steps.mpa_pre_configuration import MPAPreConfiguration

config = Config()
purchase = Pipeline(
    GetMPACredentials(config, SWO_EXTENSION_MANAGEMENT_ROLE),
    MPAPreConfiguration(),
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
