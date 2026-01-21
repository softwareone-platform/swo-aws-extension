import datetime as dt
import logging
from typing import override

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.aws.config import Config
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.constants import (
    MONTHS_PER_YEAR,
    OrderParametersEnum,
    OrderQueryingTemplateEnum,
    PhasesEnum,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.errors import (
    ERR_CREATING_INVITATION_RESPONSE,
    ERR_MISSING_MPA_ID,
    AlreadyProcessedStepError,
    QueryStepError,
    SkipStepError,
)
from swo_aws_extension.parameters import (
    get_mpa_account_id,
    get_phase,
    get_responsibility_transfer_id,
    set_ordering_parameter_error,
    set_phase,
    set_responsibility_transfer_id,
)

logger = logging.getLogger(__name__)


class CreateBillingTransferInvitation(BasePhaseStep):
    """Create Billing Transfer Invitation step."""

    def __init__(self, config: Config) -> None:
        self._config = config

    @override
    def pre_step(self, context: PurchaseContext) -> None:
        """Hook to run before the step processing."""
        phase = get_phase(context.order)
        if phase != PhasesEnum.CREATE_BILLING_TRANSFER_INVITATION:
            raise SkipStepError(
                f"{context.order_id} - Next - Current phase is '{phase}', skipping as it"
                f" is not '{PhasesEnum.CREATE_BILLING_TRANSFER_INVITATION}'"
            )

        if get_responsibility_transfer_id(context.order):
            context.order = set_phase(context.order, PhasesEnum.CHECK_BILLING_TRANSFER_INVITATION)
            raise AlreadyProcessedStepError(
                f"{context.order_id} - Next - Billing transfer invitation already created. Continue"
            )

    @override
    def process(self, client: MPTClient, context: PurchaseContext) -> None:
        """Create billing transfer invitation."""
        mpa_id = get_mpa_account_id(context.order)
        if not mpa_id:
            logger.info(
                "%s - Error - Master Payer Account ID is missing in the order parameters",
                context.order_id,
            )
            context.order = set_ordering_parameter_error(
                context.order,
                OrderParametersEnum.MASTER_PAYER_ACCOUNT_ID,
                ERR_MISSING_MPA_ID.to_dict(),
            )
            raise QueryStepError(
                f"{context.order_id} - Querying - Querying due to missing Master Payer Account ID.",
                OrderQueryingTemplateEnum.INVALID_ACCOUNT_ID,
            )
        logger.info(
            "%s - Action - Creating Billing Transfer Invitation for MPA Account ID: %s",
            context.order_id,
            mpa_id,
        )
        relationship_name = f"Transfer Billing - {context.buyer['name']}"
        try:
            invitation_handshake = context.aws_client.invite_organization_to_transfer_billing(
                customer_id=mpa_id,
                source_name=relationship_name,
                start_timestamp=self._get_start_billing_transfer_timestamp(),
            )
        except AWSError as error:
            logger.info(
                "%s - Error - Failed to invite organization to transfer billing responsibility: %s",
                context.order_id,
                error,
            )
            context.order = set_ordering_parameter_error(
                context.order,
                OrderParametersEnum.MASTER_PAYER_ACCOUNT_ID,
                ERR_CREATING_INVITATION_RESPONSE.to_dict(mpa_id=mpa_id, error=str(error)),
            )
            raise QueryStepError(
                f"{context.order_id} - Querying - Querying due to error inviting organization to"
                f" transfer billing responsibility: {error!s}",
                OrderQueryingTemplateEnum.INVALID_ACCOUNT_ID,
            )
        responsibility_transfer_id = self._get_responsibility_id_from_invitation(
            invitation_handshake
        )
        context.order = set_responsibility_transfer_id(context.order, responsibility_transfer_id)
        logger.info(
            "%s - Next - Created billing transfer invitation for account %s with Responsibility "
            "Transfer ID: %s",
            context.order_id,
            mpa_id,
            responsibility_transfer_id,
        )

    @override
    def post_step(self, client: MPTClient, context: PurchaseContext) -> None:
        """Hook to run after the step processing."""
        context.order = set_phase(context.order, PhasesEnum.CHECK_BILLING_TRANSFER_INVITATION)
        context.order = update_order(
            client, context.order_id, parameters=context.order["parameters"]
        )

    def _get_start_billing_transfer_timestamp(self) -> int:
        """Return first day of next month at 00:00 UTC as Unix timestamp."""
        now = dt.datetime.now(dt.UTC)
        year = now.year + (now.month // MONTHS_PER_YEAR)
        month = (now.month % MONTHS_PER_YEAR) + 1
        first_of_next_month = dt.datetime(year, month, 1, 0, 0, 0, tzinfo=dt.UTC)
        return int(first_of_next_month.timestamp())

    def _get_responsibility_id_from_invitation(self, invitation_handshake):
        resources = invitation_handshake["Handshake"]["Resources"]
        return next(
            resource["Value"]
            for resource in resources
            if resource.get("Type") == "RESPONSIBILITY_TRANSFER"
        )
