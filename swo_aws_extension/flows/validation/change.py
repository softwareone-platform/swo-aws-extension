import logging

from mpt_extension_sdk.flows.pipeline import Pipeline

from swo_aws_extension.flows.validation.steps import InitializeItemStep

logger = logging.getLogger(__name__)


def validate_and_setup_change_order(client, context):
    """Setup pipeline for change order."""
    logger.info("Validating Change order - %s", context.order_id)
    pipeline = Pipeline(
        InitializeItemStep(),
    )
    pipeline.run(client, context)
    return not context.validation_succeeded, context.order
