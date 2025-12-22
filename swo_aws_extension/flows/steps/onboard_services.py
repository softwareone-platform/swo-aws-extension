import logging
from typing import override

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.aws.config import Config
from swo_aws_extension.constants import (
    CRM_NEW_ACCOUNT_ADDITIONAL_INFO,
    CRM_NEW_ACCOUNT_SUMMARY,
    CRM_NEW_ACCOUNT_TITLE,
    PhasesEnum,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.errors import AlreadyProcessedStepError, SkipStepError
from swo_aws_extension.parameters import (
    get_crm_onboard_ticket_id,
    get_mpa_account_id,
    get_phase,
    set_crm_onboard_ticket_id,
    set_phase,
)
from swo_aws_extension.swo.crm_service.client import ServiceRequest, get_service_client
from swo_aws_extension.swo.crm_service.errors import CRMError

logger = logging.getLogger(__name__)


class OnboardServices(BasePhaseStep):
    """Onboard Services step."""

    def __init__(self, config: Config):
        self._config = config

    @override
    def pre_step(self, context: PurchaseContext) -> None:
        phase = get_phase(context.order)
        if phase != PhasesEnum.ONBOARD_SERVICES:
            raise SkipStepError(
                f"{context.order_id} - Next - Current phase is '{phase}', skipping as it"
                f" is not '{PhasesEnum.ONBOARD_SERVICES}'"
            )
        onboard_ticket_id = get_crm_onboard_ticket_id(context.order)
        if onboard_ticket_id:
            context.order = set_phase(context.order, PhasesEnum.CREATE_SUBSCRIPTION)
            raise AlreadyProcessedStepError(
                f"{context.order_id} - Next - Onboard services already created with ticket ID"
                f" '{onboard_ticket_id}'. Continue"
            )

    @override
    def process(self, client: MPTClient, context: PurchaseContext) -> None:
        crm_client = get_service_client()
        service_request = ServiceRequest(
            additional_info=CRM_NEW_ACCOUNT_ADDITIONAL_INFO,
            summary=CRM_NEW_ACCOUNT_SUMMARY.format(
                customer_name=context.buyer.get("name"),
                buyer_external_id=context.buyer.get("id"),
                order_id=context.order_id,
                master_payer_id=get_mpa_account_id(context.order),
            ),
            title=CRM_NEW_ACCOUNT_TITLE,
        )
        try:
            response = crm_client.create_service_request(context.order_id, service_request)
        except CRMError as error:
            logger.info(
                "%s - Failed to create onboard services ticket: %s", context.order_id, error
            )
            return
        ticket_id = response.get("id")
        if ticket_id:
            context.order = set_crm_onboard_ticket_id(context.order, ticket_id)
            logger.info(
                "%s - Onboard services ticket created with ID %s", context.order_id, ticket_id
            )
        else:
            logger.info("%s - No ticket ID returned from CRM", context.order_id)

    @override
    def post_step(self, client: MPTClient, context: PurchaseContext) -> None:
        context.order = set_phase(context.order, PhasesEnum.CREATE_SUBSCRIPTION)
        context.order = update_order(
            client, context.order_id, parameters=context.order["parameters"]
        )
