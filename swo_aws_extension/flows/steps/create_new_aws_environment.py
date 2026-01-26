import logging
from typing import override

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.aws.config import Config
from swo_aws_extension.constants import (
    OrderParametersEnum,
    OrderQueryingTemplateEnum,
    PhasesEnum,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.errors import (
    ERR_MISSING_MPA_ID,
    QueryStepError,
    SkipStepError,
)
from swo_aws_extension.parameters import (  # noqa: WPS235
    get_mpa_account_id,
    get_phase,
    set_ordering_parameter_error,
    set_phase,
)

logger = logging.getLogger(__name__)


class CreateNewAWSEnvironment(BasePhaseStep):
    """Handles the creation of a new AWS environment."""

    def __init__(self, config: Config):
        self._config = config

    @override
    def pre_step(self, context: PurchaseContext) -> None:
        phase = get_phase(context.order)
        if phase != PhasesEnum.CREATE_NEW_AWS_ENVIRONMENT:
            raise SkipStepError(
                f"{context.order_id} - Next - Current phase is '{phase}', skipping as it"
                f" is not '{PhasesEnum.CREATE_NEW_AWS_ENVIRONMENT}'"
            )

    @override
    def process(self, client: MPTClient, context: PurchaseContext) -> None:
        logger.info(
            "%s - Intent - Checking if new AWS environment has been created manually",
            context.order_id,
        )
        mpa_id = get_mpa_account_id(context.order)
        if not mpa_id:
            logger.info(
                "%s - Warning - Master Payer Account ID is missing in the order parameters",
                context.order_id,
            )
            context.order = set_ordering_parameter_error(
                context.order,
                OrderParametersEnum.MASTER_PAYER_ACCOUNT_ID,
                ERR_MISSING_MPA_ID.to_dict(),
            )
            raise QueryStepError(
                f"{context.order_id} - Querying - Querying due to missing Master Payer Account ID.",
                OrderQueryingTemplateEnum.NEW_ACCOUNT_CREATION,
            )
        logger.info(
            "%s - Next - Create New AWS Environment completed successfully", context.order_id
        )

    @override
    def post_step(self, client: MPTClient, context: PurchaseContext) -> None:
        context.order = set_phase(context.order, PhasesEnum.CREATE_BILLING_TRANSFER_INVITATION)
        context.order = update_order(
            client, context.order_id, parameters=context.order["parameters"]
        )
