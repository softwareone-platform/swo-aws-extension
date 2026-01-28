import logging
from typing import override

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.config import Config
from swo_aws_extension.constants import (
    OrderProcessingTemplateEnum,
    PhasesEnum,
)
from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.order_utils import update_processing_template_and_notify
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.errors import ConfigurationStepError, UnexpectedStopError
from swo_aws_extension.parameters import get_phase, set_phase

logger = logging.getLogger(__name__)


class SetupContext(BasePhaseStep):
    """Initial setup context step."""

    def __init__(self, config: Config) -> None:
        self._config = config

    @override
    def pre_step(self, context: InitialAWSContext) -> None:
        if not context.pm_account_id:
            raise ConfigurationStepError(
                "Setup context",
                "SetupContextError - PMA account is required to setup AWS Client in context",
            )

    @override
    def process(self, client: MPTClient, context: InitialAWSContext) -> None:
        self._init_processing_template(client, context)
        try:
            context.aws_client = AWSClient(
                self._config, context.pm_account_id, self._config.management_role_name
            )
        except AWSError as error:
            raise UnexpectedStopError(
                f"Program Management Account {context.pm_account_id} failed to retrieve "
                f"credentials",
                f"The Program Management Account {context.pm_account_id} is failing "
                f"to provide valid AWS credentials with error: {error!s}. Please verify that "
                f"the account ID is correct",
            ) from error
        apn_account_id = self._config.apn_account_id
        apn_role_name = self._config.apn_role_name
        try:
            context.aws_apn_client = AWSClient(self._config, apn_account_id, apn_role_name)
        except AWSError as error:
            raise UnexpectedStopError(
                f"APN Account {apn_account_id} failed to retrieve credentials",
                f"The APN Account {apn_account_id} is failing to provide valid "
                f"AWS credentials with error: {error!s}. Please verify that role "
                f"{apn_role_name} is created",
            ) from error
        logger.info("%s - Next - SetupContext completed successfully", context.order_id)

    @override
    def post_step(self, client: MPTClient, context: InitialAWSContext) -> None:
        phase = get_phase(context.order)
        if not phase:
            next_phase = (
                PhasesEnum.CREATE_NEW_AWS_ENVIRONMENT
                if context.is_type_new_aws_environment()
                else PhasesEnum.CREATE_BILLING_TRANSFER_INVITATION
            )
            context.order = set_phase(context.order, next_phase)
            context.order = update_order(
                client, context.order_id, parameters=context.order["parameters"]
            )

    def _init_processing_template(self, client: MPTClient, context: InitialAWSContext) -> None:
        template_name = ""
        if context.is_purchase_order():
            if context.is_type_new_aws_environment():
                template_name = OrderProcessingTemplateEnum.NEW_ACCOUNT
            else:
                template_name = OrderProcessingTemplateEnum.EXISTING_ACCOUNT
        elif context.is_termination_order():
            template_name = OrderProcessingTemplateEnum.TERMINATE

        if template_name and context.template["name"] != template_name:
            update_processing_template_and_notify(client, context, template_name)
