import logging
from collections.abc import Callable
from typing import Any

from mpt_extension_sdk.flows.pipeline import Step
from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.aws.config import Config
from swo_aws_extension.flows.order import (
    InitialAWSContext,
)

logger = logging.getLogger(__name__)


class SetupContext(Step):
    """Initial setup context step."""

    def __init__(self, config: Config, role_name: str) -> None:
        self._config = config
        self._role_name = role_name

    def __call__(
        self,
        client: MPTClient,
        context: InitialAWSContext,
        next_step: Callable[[MPTClient, InitialAWSContext], Any],
    ) -> None:
        """Execute step."""
        self.setup_aws(context)
        logger.info("%s - Next - SetupContext completed successfully", context.order_id)
        next_step(client, context)

    def setup_aws(self, context: InitialAWSContext) -> None:
        """Initialize AWS client."""
        if not context.pm_account_id:
            raise ValueError(
                "SetupContextError - PMA account is required to setup AWS Client in context"
            )

        context.aws_client = AWSClient(self._config, context.pm_account_id, self._role_name)
        logger.info(
            "%s - Action - PMA credentials for %s retrieved successfully",
            context.order_id,
            context.pm_account_id,
        )


class SetupPurchaseContext(SetupContext):
    """Setup Context for purchase order."""

    def __call__(
        self,
        client: MPTClient,
        context: InitialAWSContext,
        next_step: Callable[[MPTClient, InitialAWSContext], Any],
    ) -> None:
        """Execute step."""
        if context.pm_account_id:
            self.setup_aws(context)

        logger.info("%s - Next - SetupPurchaseContext completed successfully", context.order_id)

        next_step(client, context)
