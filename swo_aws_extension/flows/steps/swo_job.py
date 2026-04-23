import logging
from typing import override

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.errors import SkipStepError
from swo_aws_extension.parameters import (
    get_cco_contract_number,
    get_formatted_technical_contact,
    get_phase,
    set_erp_project_no,
    set_phase,
)
from swo_aws_extension.swo.cco.errors import SellerCountryNotFoundError
from swo_aws_extension.swo.cco.seller_mapper import SellerMapper
from swo_aws_extension.swo.notifications.teams import notify_one_time_error
from swo_aws_extension.swo.service_provisioning.client import get_service_provisioning_client
from swo_aws_extension.swo.service_provisioning.errors import ServiceProvisioningError
from swo_aws_extension.swo.service_provisioning.models import (
    ServiceContact,
    ServiceOnboardingRequest,
)

logger = logging.getLogger(__name__)

_SWO_JOB_SERVICE_DESCRIPTION = "SN00518"
_SWO_JOB_DEFAULT_LANGUAGE_CODE = "en"


class SWOJobStep(BasePhaseStep):
    """SWO Job creation step.

    Creates a SWO Job using the CCO contract number stored in the
    `ccoContractNumber` fulfillment parameter and saves the resulting
    project number in `erpProjectNo`. Then advances the phase to
    `CREATE_SUBSCRIPTION`.

    Errors are logged and notified to MS Teams but never block order
    fulfillment.
    """

    @override
    def pre_step(self, context: PurchaseContext) -> None:
        phase = get_phase(context.order)
        if phase != PhasesEnum.PROJECT_CREATION:
            raise SkipStepError(
                f"{context.order_id} - Next - Current phase is '{phase}', skipping as it"
                f" is not '{PhasesEnum.PROJECT_CREATION}'"
            )

    @override
    def process(self, client: MPTClient, context: PurchaseContext) -> None:
        contract_number = get_cco_contract_number(context.order)
        if not contract_number:
            logger.warning(
                "%s - SWOJobStep - ccoContractNumber is not set; cannot create SWO Job",
                context.order_id,
            )
            notify_one_time_error(
                f"SWOJobStep error for order {context.order_id}",
                f"Cannot create SWO Job for order `{context.order_id}` because "
                "`ccoContractNumber` is not set. "
                "Processing continues to the next step.",
            )
            return

        logger.info(
            "%s - Action - Creating SWO Job for CCO contract %s",
            context.order_id,
            contract_number,
        )

        try:
            erp_project_no = self._create_swo_job(context, contract_number)
        except SellerCountryNotFoundError:
            seller_country = context.seller.get("address", {}).get("country", "")
            logger.exception(
                "%s - SellerCountryNotFoundError - No legal entity mapping for seller country '%s'",
                context.order_id,
                seller_country,
            )
            notify_one_time_error(
                f"SWOJobStep error for order {context.order_id}",
                f"No SoftwareOne legal entity mapping found for seller country "
                f"`{seller_country}` on order `{context.order_id}`. "
                "Processing continues to the next step.",
            )
            return
        except ServiceProvisioningError:
            logger.exception(
                "%s - ServiceProvisioningError - Failed to create SWO Job for contract %s",
                context.order_id,
                contract_number,
            )
            notify_one_time_error(
                f"SWOJobStep error for order {context.order_id}",
                f"Failed to create SWO Job for CCO contract `{contract_number}` "
                f"on order `{context.order_id}`. "
                "Processing continues to the next step.",
            )
            return

        context.order = set_erp_project_no(context.order, erp_project_no)
        logger.info(
            "%s - Next - SWO Job created with ERP project number %s",
            context.order_id,
            erp_project_no,
        )

    @override
    def post_step(self, client: MPTClient, context: PurchaseContext) -> None:
        context.order = set_phase(context.order, PhasesEnum.COMPLETED)
        context.order = update_order(
            client, context.order_id, parameters=context.order["parameters"]
        )

    def _create_swo_job(self, context: PurchaseContext, contract_number: str) -> str:
        """Call Service Provisioning API and return the erpProjectNo."""
        contact_info = get_formatted_technical_contact(context.order)
        name_parts = contact_info.get("name", "").split(" ", 1)
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        email = contact_info.get("email", "")
        phone = contact_info.get("phone", "")

        seller_country = context.seller.get("address", {}).get("country", "")
        software_one_legal_entity = SellerMapper().map(seller_country)
        request = ServiceOnboardingRequest(
            erp_client_id=software_one_legal_entity,
            contract_no=contract_number,
            service_description=_SWO_JOB_SERVICE_DESCRIPTION,
            contacts=[
                ServiceContact(
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    phone_number=phone,
                    language_code=_SWO_JOB_DEFAULT_LANGUAGE_CODE,
                )
            ],
        )

        logger.info(
            "%s - Action - Calling Service Provisioning API to create SWO Job",
            context.order_id,
        )
        response = get_service_provisioning_client().onboard(request)
        return response.erp_project_no
