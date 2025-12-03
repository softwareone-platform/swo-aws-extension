import logging
from collections.abc import Callable
from typing import Any

from mpt_extension_sdk.flows.pipeline import Step
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.airtable.errors import AirtableRecordNotFoundError
from swo_aws_extension.airtable.models import PMARecord
from swo_aws_extension.airtable.pma_table import ProgramManagementAccountTable
from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.aws.config import Config
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.notifications import notify_one_time_error_in_teams
from swo_aws_extension.parameters import get_phase, set_phase, set_pm_account_id

logger = logging.getLogger(__name__)


class AssignPMA(Step):
    """Assign Program Management account to the order."""

    def __init__(self, config: Config, role_name: str) -> None:
        self._config = config
        self._role_name = role_name

    def __call__(
        self,
        client: MPTClient,
        context: PurchaseContext,
        next_step: Callable[[MPTClient, PurchaseContext], Any],
    ) -> None:
        """Execute step."""
        phase = get_phase(context.order)
        if phase and phase != PhasesEnum.ASSIGN_PMA:
            logger.info(
                "%s - Next - Current phase is '%s', skipping as it is not '%s'",
                context.order_id,
                phase,
                PhasesEnum.ASSIGN_PMA.value,
            )
            next_step(client, context)
            return

        if context.pm_account_id:
            context.order = set_phase(context.order, PhasesEnum.CREATE_ACCOUNT)
            context.order = update_order(
                client, context.order_id, parameters=context.order["parameters"]
            )
            logger.info(
                "%s - Next - PMA account %s already assigned to order %s. Continue",
                context.order_id,
                context.pm_account_id,
                context.order_id,
            )
            next_step(client, context)
            return

        pma_table = ProgramManagementAccountTable()
        try:
            pm_account = pma_table.get_by_authorization_and_currency_id(
                context.authorization_id, context.currency
            )
        except AirtableRecordNotFoundError:
            logger.exception(
                "%s - Error - No PMA found for Authorization ID %s and currency %s",
                context.order_id,
                context.authorization_id,
                context.currency,
            )
            notify_one_time_error_in_teams(
                f"No Program Management Account found for Authorization ID "
                f"{context.authorization_id}",
                f"Failed to find a Program Management Account for "
                f"Authorization ID {context.authorization_id} and currency {context.currency}. "
                f"Please ensure that a valid PMA exists in Airtable.",
            )
            return

        context.aws_client = AWSClient(self._config, pm_account.pma_account_id, self._role_name)
        if not self._validate_pma_credentials(context, pm_account):
            return

        context.order = set_phase(context.order, PhasesEnum.CREATE_ACCOUNT)
        context.order = set_pm_account_id(context.order, pm_account.pma_account_id)
        context.order = update_order(
            client, context.order_id, parameters=context.order["parameters"]
        )

        logger.info(
            "%s - Next - Program Management Account %s assigned.",
            context.order_id,
            context.pm_account_id,
        )
        next_step(client, context)

    def _validate_pma_credentials(self, context: PurchaseContext, pm_account: PMARecord) -> bool:
        try:
            context.aws_client.get_caller_identity()
        except AWSError as error:
            logger.exception(
                "%s - Error - Failed to retrieve PMA credentials for %s.",
                context.order_id,
                pm_account.pma_account_id,
            )
            notify_one_time_error_in_teams(
                f"Master Payer account {pm_account.pma_account_id} failed to retrieve credentials",
                f"The Master Payer Account {pm_account.pma_account_id} is failing "
                f"with error: {error!s}",
            )
            return False

        logger.info(
            "%s - Action - PMA credentials for %s retrieved successfully",
            context.order_id,
            pm_account.pma_account_id,
        )
        return True
