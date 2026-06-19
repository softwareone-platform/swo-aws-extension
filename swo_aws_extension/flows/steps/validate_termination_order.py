import logging
from typing import override

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.utils import find_first

from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.errors import FailStepError

logger = logging.getLogger(__name__)


class ValidateTerminationOrder(BasePhaseStep):
    """Validate termination order before processing."""

    @override
    def pre_step(self, context: InitialAWSContext) -> None: ...

    @override
    def process(self, client: MPTClient, context: InitialAWSContext) -> None:
        logger.info("%s - Validating termination order", context.order_id)
        master_id = context.master_payer_account_id
        master_subscription = find_first(
            lambda sub: sub.get("externalIds", {}).get("vendor") == master_id,
            context.subscriptions,
            default=None,
        )
        if not master_subscription or master_subscription.get("status") != "Terminating":
            raise FailStepError(
                "AWS005",
                "Termination orders on linked-account subscriptions are not supported. "
                "Only the master payer subscription can be terminated.",
            )

    @override
    def post_step(self, client: MPTClient, context: InitialAWSContext) -> None:
        logger.info("%s - Next - ValidateTerminationOrder completed successfully", context.order_id)
