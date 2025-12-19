import logging
from typing import override

from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.aws.config import Config
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.errors import ConfigurationStepError, UnexpectedStopError
from swo_aws_extension.parameters import get_phase, set_phase

logger = logging.getLogger(__name__)


class SetupContext(BasePhaseStep):
    """Initial setup context step."""

    def __init__(self, config: Config, role_name: str) -> None:
        self._config = config
        self._role_name = role_name

    @override
    def pre_step(self, context: InitialAWSContext) -> None:
        if not context.pm_account_id:
            raise ConfigurationStepError(
                "SetupContextError - PMA account is required to setup AWS Client in context"
            )

    @override
    def process(self, context: InitialAWSContext) -> None:
        try:
            context.aws_client = AWSClient(self._config, context.pm_account_id, self._role_name)
        except AWSError as error:
            raise UnexpectedStopError(
                f"Program Management Account {context.pm_account_id} failed to retrieve "
                f"credentials",
                f"The Program Management Account {context.pm_account_id} is failing "
                f"to provide valid AWS credentials with error: {error!s}. Please verify that "
                f"the account ID is correct",
            )
        logger.info("%s - Next - SetupContext completed successfully", context.order_id)

    @override
    def post_step(self, context: InitialAWSContext) -> None:
        phase = get_phase(context.order)
        if not phase:
            next_phase = (
                PhasesEnum.CREATE_ACCOUNT
                if context.is_type_new_aws_environment()
                else PhasesEnum.CREATE_BILLING_TRANSFER_INVITATION
            )
            context.order = set_phase(context.order, next_phase)
            context.order = update_order(
                self._client, context.order_id, parameters=context.order["parameters"]
            )
