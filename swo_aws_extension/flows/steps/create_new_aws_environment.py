import logging
from typing import override

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.aws.config import Config
from swo_aws_extension.constants import (
    CRM_NEW_ACCOUNT_ADDITIONAL_INFO,
    CRM_NEW_ACCOUNT_SUMMARY,
    CRM_NEW_ACCOUNT_TITLE,
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
    UnexpectedStopError,
)
from swo_aws_extension.parameters import (  # noqa: WPS235
    get_cost_management,
    get_crm_new_account_ticket_id,
    get_mpa_account_id,
    get_order_account_email,
    get_order_account_name,
    get_phase,
    get_resold_support_plans,
    get_supplementary_services,
    get_support_type,
    get_technical_contact_info,
    set_crm_new_account_ticket_id,
    set_ordering_parameter_error,
    set_phase,
)
from swo_aws_extension.swo.crm_service.client import ServiceRequest, get_service_client
from swo_aws_extension.swo.crm_service.errors import CRMError

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
        logger.info("%s - Intent - Creating new AWS environment", context.order_id)
        new_account_ticket_id = get_crm_new_account_ticket_id(context.order)
        if not new_account_ticket_id:
            self._create_new_account_ticket(context)

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

    def _create_new_account_ticket(self, context: PurchaseContext):
        crm_client = get_service_client()
        service_request = ServiceRequest(
            additional_info=CRM_NEW_ACCOUNT_ADDITIONAL_INFO,
            summary=CRM_NEW_ACCOUNT_SUMMARY.format(
                customer_name=context.buyer.get("name"),
                buyer_external_id=context.buyer.get("id"),
                order_id=context.order_id,
                order_account_name=get_order_account_name(context.order),
                order_account_email=get_order_account_email(context.order),
                technical_contact=get_technical_contact_info(context.order),
                support_type=get_support_type(context.order),
                resold_support_plans=get_resold_support_plans(context.order),
                cost_management=get_cost_management(context.order),
                supplementary_services=get_supplementary_services(context.order),
            ),
            title=CRM_NEW_ACCOUNT_TITLE,
        )
        try:
            response = crm_client.create_service_request(context.order_id, service_request)
        except CRMError as error:
            logger.info("%s - Failed to create New Account ticket: %s", context.order_id, error)
            raise UnexpectedStopError(
                "Error creating New Account ticket", f"Error details: {error}"
            ) from error
        ticket_id = response.get("id")
        if ticket_id:
            context.order = set_crm_new_account_ticket_id(context.order, ticket_id)
            logger.info("%s - New account ticket created with ID %s", context.order_id, ticket_id)
        else:
            logger.info("%s - No ticket ID returned from CRM", context.order_id)
