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
    get_phase,
    get_technical_contact_info,
    set_erp_project_no,
    set_phase,
)
from swo_aws_extension.swo.notifications.teams import TeamsNotificationManager
from swo_aws_extension.swo.service_provisioning.client import get_service_provisioning_client
from swo_aws_extension.swo.service_provisioning.errors import ServiceProvisioningError
from swo_aws_extension.swo.service_provisioning.models import (
    ServiceContact,
    ServiceOnboardingRequest,
)

logger = logging.getLogger(__name__)

_SWO_JOB_SERVICE_DESCRIPTION = "AWS Marketplace Service Activation"


class SWOJobStep(BasePhaseStep):
    """SWO Job creation step.

    Creates a SWO Job using the CCO contract number stored in the
    ``ccoContractNumber`` fulfillment parameter and saves the resulting
    project number in ``erpProjectNo``. Then advances the phase to
    ``CREATE_SUBSCRIPTION``.

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

    @override
    def process(self, client: MPTClient, context: PurchaseContext) -> None:
        contract_number = get_cco_contract_number(context.order)
        if not contract_number:
            logger.warning(
                "%s - SWOJobStep - ccoContractNumber is not set; cannot create SWO Job",
                context.order_id,
            )
            TeamsNotificationManager().send_error(
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
        except ServiceProvisioningError:
            logger.exception(
                "%s - ServiceProvisioningError - Failed to create SWO Job for contract %s",
                context.order_id,
                contract_number,
            )
            TeamsNotificationManager().send_error(
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
        context.order = set_phase(context.order, PhasesEnum.CREATE_SUBSCRIPTION.value)
        context.order = update_order(
            client, context.order_id, parameters=context.order["parameters"]
        )

    def _create_swo_job(self, context: PurchaseContext, contract_number: str) -> str:
        """Call Service Provisioning API and return the erpProjectNo."""
        contact_info = get_technical_contact_info(context.order)
        first_name = contact_info.get("firstName", "")
        last_name = contact_info.get("lastName", "")
        email = contact_info.get("email", "")
        phone = contact_info.get("phone", "")

        # Handle phone as dict (prefix + number) or string
        if isinstance(phone, dict):
            phone = f"{phone.get('prefix', '')}{phone.get('number', '')}"

        buyer_erp_id = context.buyer.get("externalIds", {}).get("erpCustomer", "")

        request = ServiceOnboardingRequest(
            erp_client_id=buyer_erp_id,
            contract_no=contract_number,
            service_description=_SWO_JOB_SERVICE_DESCRIPTION,
            contacts=[
                ServiceContact(
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    phone_number=phone,
                    language_code="en",
                )
            ],
        )
        response = get_service_provisioning_client().onboard(request)
        return response.erp_project_no
