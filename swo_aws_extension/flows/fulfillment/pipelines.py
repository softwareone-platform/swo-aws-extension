from mpt_extension_sdk.flows.pipeline import Pipeline

from swo_aws_extension.aws.config import Config
from swo_aws_extension.constants import SWO_EXTENSION_MANAGEMENT_ROLE
from swo_aws_extension.flows.steps.assign_pma import AssignPMA
from swo_aws_extension.flows.steps.setup_context import SetupPurchaseContext

config = Config()

purchase_new_aws_environment = Pipeline(
    SetupPurchaseContext(config, SWO_EXTENSION_MANAGEMENT_ROLE),
    AssignPMA(config, SWO_EXTENSION_MANAGEMENT_ROLE),
)

purchase_existing_aws_environment = Pipeline(
    SetupPurchaseContext(config, SWO_EXTENSION_MANAGEMENT_ROLE),
    AssignPMA(config, SWO_EXTENSION_MANAGEMENT_ROLE),
)
