import datetime as dt
import logging
from typing import override

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.config import Config
from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.errors import SkipStepError
from swo_aws_extension.parameters import (
    get_cco_contract_number,
    get_mpa_account_id,
    get_phase,
    set_cco_contract_number,
)
from swo_aws_extension.swo.cco.client import get_cco_client
from swo_aws_extension.swo.cco.errors import CcoError
from swo_aws_extension.swo.cco.models import CreateCcoRequest
from swo_aws_extension.swo.notifications.teams import TeamsNotificationManager

logger = logging.getLogger(__name__)


class ContractCardStep(BasePhaseStep):
    """Contract Card (CCO) step.

    Checks whether the MPA account already has a CCO contract; loads the
    existing one or creates a new one. Saves the contract number in the
    ``ccoContractNumber`` fulfillment parameter.

    Errors are logged and notified to MS Teams but never block order
    fulfillment.
    """

    def __init__(self, config: Config) -> None:
        self._config = config

    @override
    def pre_step(self, context: PurchaseContext) -> None:
        phase = get_phase(context.order)
        if phase != PhasesEnum.PROJECT_CREATION:
            raise SkipStepError(
                f"{context.order_id} - Next - Current phase is '{phase}', skipping as it"
                f" is not '{PhasesEnum.PROJECT_CREATION}'"
            )
        if get_cco_contract_number(context.order):
            raise SkipStepError(
                f"{context.order_id} - Next - CCO contract number is already set, skipping"
            )

    @override
    def process(self, client: MPTClient, context: PurchaseContext) -> None:
        mpa_id = get_mpa_account_id(context.order)
        logger.info(
            "%s - Action - Looking up CCO contract for MPA account %s",
            context.order_id,
            mpa_id,
        )

        try:
            contracts = get_cco_client().get_all_contracts(mpa_id)
        except CcoError:
            logger.exception(
                "%s - CcoError - Failed to retrieve contracts for MPA %s",
                context.order_id,
                mpa_id,
            )
            TeamsNotificationManager().send_error(
                f"ContractCardStep error for order {context.order_id}",
                f"Failed to retrieve CCO contracts for MPA account `{mpa_id}` "
                f"on order `{context.order_id}`. "
                "Processing continues to the next step.",
            )
            return

        if contracts:
            contract_number = contracts[0].contract_number
            logger.info(
                "%s - Next - Found existing CCO contract %s",
                context.order_id,
                contract_number,
            )
        else:
            logger.info(
                "%s - Action - No CCO contract found; creating a new one for MPA %s",
                context.order_id,
                mpa_id,
            )
            try:
                contract_number = self._create_contract(context, mpa_id)
            except CcoError:
                logger.exception(
                    "%s - CcoError - Failed to create CCO contract for MPA %s",
                    context.order_id,
                    mpa_id,
                )
                TeamsNotificationManager().send_error(
                    f"ContractCardStep error for order {context.order_id}",
                    f"Failed to create CCO contract for MPA account `{mpa_id}` "
                    f"on order `{context.order_id}`. "
                    "Processing continues to the next step.",
                )
                return

        context.order = set_cco_contract_number(context.order, contract_number)
        logger.info(
            "%s - Next - CCO contract number %s saved",
            context.order_id,
            contract_number,
        )

    @override
    def post_step(self, client: MPTClient, context: PurchaseContext) -> None:
        context.order = update_order(
            client, context.order_id, parameters=context.order["parameters"]
        )

    def _create_contract(self, context: PurchaseContext, mpa_id: str) -> str:
        """Create a new CCO contract and return its contract number."""
        buyer_erp_id = context.buyer.get("externalIds", {}).get("erpCustomer", "")
        currency = context.currency or "USD"

        request = CreateCcoRequest(
            software_one_legal_entity=context.seller.get("id", ""),
            contract_number_reference=mpa_id,
            customer_number=buyer_erp_id,
            enrollment_number=context.authorization_id or mpa_id,
            manufacturer_code="AWS",
            start_date=dt.datetime.now(dt.UTC),
            currency_code=currency,
            license_model="SAAS",
        )
        response = get_cco_client().create_cco(request)
        logger.info(
            "%s - Next - Created CCO contract %s",
            context.order_id,
            response.contract_number,
        )
        return response.contract_number
