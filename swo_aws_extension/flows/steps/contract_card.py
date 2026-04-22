import datetime as dt
import json
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
from swo_aws_extension.swo.notifications.teams import notify_one_time_error

logger = logging.getLogger(__name__)


def map_software_one_legal_entity(seller_country: str, config: Config) -> str:
    """Map a seller country code to the SoftwareOne legal entity identifier.

    Args:
        seller_country: ISO country code from the seller address.
        config: Extension configuration providing the map file path.

    Returns:
        The SoftwareOne legal entity string for the given country.

    Raises:
        KeyError: If the country code is not present in the map.
    """
    mapping: dict[str, str] = json.loads(config.cco_seller_map_path.read_text(encoding="utf-8"))
    return mapping[seller_country.upper()]


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
            notify_one_time_error(
                f"ContractCardStep error for order {context.order_id}",
                f"Failed to retrieve CCO contracts for MPA account `{mpa_id}` "
                f"on order `{context.order_id}`. "
                "Processing continues to the next step.",
            )
            return

        contract_number = self._resolve_contract_number(context, mpa_id, contracts)
        if contract_number is None:
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

    def _resolve_contract_number(
        self,
        context: PurchaseContext,
        mpa_id: str,
        contracts: list,
    ) -> str | None:
        """Return an existing contract number or create a new one.

        Returns None if contract creation failed (error already logged/notified).
        """
        if contracts:
            contract_number = contracts[0].contract_number
            logger.info(
                "%s - Next - Found existing CCO contract %s",
                context.order_id,
                contract_number,
            )
            return contract_number

        logger.info(
            "%s - Action - No CCO contract found; creating a new one for MPA %s",
            context.order_id,
            mpa_id,
        )
        try:
            return self._create_contract(context, mpa_id)
        except KeyError:
            seller_country = context.seller.get("address", {}).get("country", "")
            logger.exception(
                "%s - KeyError - No legal entity mapping for seller country '%s'",
                context.order_id,
                seller_country,
            )
            notify_one_time_error(
                f"ContractCardStep error for order {context.order_id}",
                f"No SoftwareOne legal entity mapping found for seller country "
                f"`{seller_country}` on order `{context.order_id}`. "
                "Processing continues to the next step.",
            )
        except CcoError:
            logger.exception(
                "%s - CcoError - Failed to create CCO contract for MPA %s",
                context.order_id,
                mpa_id,
            )
            notify_one_time_error(
                f"ContractCardStep error for order {context.order_id}",
                f"Failed to create CCO contract for MPA account `{mpa_id}` "
                f"on order `{context.order_id}`. "
                "Processing continues to the next step.",
            )
        return None

    def _create_contract(self, context: PurchaseContext, mpa_id: str) -> str:
        """Create a new CCO contract and return its contract number."""
        buyer_erp_id = context.buyer.get("externalIds", {}).get("erpCustomer", "")
        agreement_id = context.agreement.get("id", "")
        customer_reference = context.agreement.get("externalIds", {}).get("customer", "")
        manufacturer_code = context.agreement.get("externalIds", {}).get("vendor", "")

        currency = context.currency or "USD"
        seller_country = context.seller.get("address", {}).get("country", "")
        software_one_legal_entity = map_software_one_legal_entity(seller_country, self._config)

        request = CreateCcoRequest(
            software_one_legal_entity=software_one_legal_entity,
            contract_number_reference=mpa_id,
            customer_number=buyer_erp_id,
            customer_reference=customer_reference,
            enrollment_number=agreement_id,
            manufacturer_code=manufacturer_code,
            start_date=dt.datetime.now(dt.UTC),
            currency_code=currency,
            license_model="CAW-0046",
            contract_category="CLOUD-BASI",
        )
        try:
            response = get_cco_client().create_cco(request)
        except CcoError as error:
            logger.exception(
                "%s - CcoError - Failed to create CCO contract via API for MPA %s",
                context.order_id,
                mpa_id,
            )
            notify_one_time_error(
                "Error processing Contract Card step",
                f"{context.order_id} - Error creating CCO contract for MPA account "
                f"{mpa_id}: {error!s}",
            )
            raise
        logger.info(
            "%s - Action - Created CCO contract %s",
            context.order_id,
            response.contract_number,
        )
        return response.contract_number
