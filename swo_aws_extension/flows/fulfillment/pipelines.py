import logging
import re
import traceback

from mpt_extension_sdk.flows.context import Context
from mpt_extension_sdk.flows.pipeline import Pipeline

from swo_aws_extension.aws.config import Config
from swo_aws_extension.constants import SWO_EXTENSION_MANAGEMENT_ROLE
from swo_aws_extension.flows.steps.setup_context import SetupContext
from swo_aws_extension.notifications import TeamsNotificationManager

config = Config()
logger = logging.getLogger(__name__)

TRACE_ID_REGEX = re.compile(r"(\(00-[0-9a-f]{32}-[0-9a-f]{16}-01\))")


def strip_trace_id(traceback_msg: str) -> str:
    """Strip trace id."""
    return TRACE_ID_REGEX.sub("(<omitted>)", traceback_msg)


# TODO This function is used to notify about unhandled exceptions in AWS pipelines.
# Should be removed with the new SDK error handling mechanism.
def pipeline_error_handler(error: Exception, context: Context, next_step):
    """Custom error handler for AWS pipelines."""
    logger.error("%s - Unexpected error in AWS pipeline: %s", context.order_id, str(error))
    traceback_id = strip_trace_id(traceback.format_exc())
    TeamsNotificationManager().notify_one_time_error(
        "Order fulfillment unhandled exception!",
        f"An unhandled exception has been raised while performing fulfillment "
        f"of the order **{context.order_id}**:\n\n"
        f"```{traceback_id}```",
    )
    raise error


purchase_new_aws_environment = Pipeline(
    SetupContext(config, SWO_EXTENSION_MANAGEMENT_ROLE),
)

purchase_existing_aws_environment = Pipeline(
    SetupContext(config, SWO_EXTENSION_MANAGEMENT_ROLE),
)
