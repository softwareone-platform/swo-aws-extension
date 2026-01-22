import logging
from typing import override

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.config import Config
from swo_aws_extension.constants import (
    CRM_TICKET_RESOLVED_STATE,
    CUSTOMER_ROLES_NOT_DEPLOYED_MESSAGE,
    CustomerRolesDeployed,
    OrderQueryingTemplateEnum,
    PhasesEnum,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.crm_tickets.templates.deploy_roles import DEPLOY_ROLES_TEMPLATE
from swo_aws_extension.flows.steps.errors import QueryStepError, SkipStepError, UnexpectedStopError
from swo_aws_extension.parameters import (
    get_crm_customer_role_ticket_id,
    get_formatted_technical_contact,
    get_mpa_account_id,
    get_phase,
    set_crm_customer_role_ticket_id,
    set_customer_roles_deployed,
    set_phase,
)
from swo_aws_extension.swo.crm_service.client import ServiceRequest, get_service_client
from swo_aws_extension.swo.crm_service.errors import CRMError

logger = logging.getLogger(__name__)


class CheckCustomerRoles(BasePhaseStep):
    """Check Customer Roles step."""

    def __init__(self, config: Config) -> None:
        self._config = config

    @override
    def pre_step(self, context: PurchaseContext) -> None:
        phase = get_phase(context.order)
        if phase != PhasesEnum.CHECK_CUSTOMER_ROLES:
            raise SkipStepError(
                f"{context.order_id} - Next - Current phase is '{phase}', skipping as it"
                f" is not '{PhasesEnum.CHECK_CUSTOMER_ROLES}'"
            )

    @override
    def process(self, client: MPTClient, context: PurchaseContext) -> None:
        """Check customer roles logic."""
        if self._are_customer_roles_deployed(context):
            logger.info("%s - Next - Customer roles are deployed", context.order_id)
            context.order = set_customer_roles_deployed(context.order, CustomerRolesDeployed.YES)
        else:
            context.order = set_customer_roles_deployed(
                context.order, CustomerRolesDeployed.NO_DEPLOYED
            )
            if not self._has_open_ticket(context):
                self._create_customer_role_ticket(context)
            raise QueryStepError(
                CUSTOMER_ROLES_NOT_DEPLOYED_MESSAGE,
                OrderQueryingTemplateEnum.WAITING_FOR_CUSTOMER_ROLES,
            )

    @override
    def post_step(self, client: MPTClient, context: PurchaseContext) -> None:
        """Hook to run after the step processing."""
        context.order = set_phase(context.order, PhasesEnum.ONBOARD_SERVICES)
        context.order = update_order(
            client, context.order_id, parameters=context.order["parameters"]
        )

    def _create_customer_role_ticket(self, context: PurchaseContext) -> None:
        crm_client = get_service_client()
        contact = get_formatted_technical_contact(context.order)
        service_request = ServiceRequest(
            additional_info=DEPLOY_ROLES_TEMPLATE.additional_info,
            summary=DEPLOY_ROLES_TEMPLATE.summary.format(
                customer_name=context.buyer.get("name"),
                buyer_id=context.buyer.get("id"),
                buyer_external_id=context.buyer.get("externalIds", {}).get("erpCustomer", ""),
                order_id=context.order_id,
                master_payer_id=get_mpa_account_id(context.order),
                technical_contact_name=contact["name"],
                technical_contact_email=contact["email"],
                technical_contact_phone=contact["phone"],
            ),
            title=DEPLOY_ROLES_TEMPLATE.title,
        )
        try:
            response = crm_client.create_service_request(context.order_id, service_request)
        except CRMError as error:
            logger.info(
                "%s - Failed to create pending customer roles ticket: %s", context.order_id, error
            )
            raise UnexpectedStopError(
                "Error creating pending customer roles ticket", f"Error details: {error}"
            ) from error
        if response.get("id"):
            context.order = set_crm_customer_role_ticket_id(context.order, response.get("id"))
            logger.info(
                "%s - Pending customer roles ticket created with ID %s",
                context.order_id,
                response.get("id"),
            )
        else:
            logger.info("%s - No ticket ID returned from CRM", context.order_id)

    def _has_open_ticket(self, context: PurchaseContext) -> bool:
        """Check if there's an existing open ticket for customer roles."""
        ticket_id = get_crm_customer_role_ticket_id(context.order)
        if not ticket_id:
            return False

        crm_client = get_service_client()
        ticket = crm_client.get_service_request(context.order_id, ticket_id)
        if ticket.get("state") != CRM_TICKET_RESOLVED_STATE:
            logger.info(
                "%s - Customer role ticket %s is still open",
                context.order_id,
                ticket_id,
            )
            return True

        logger.info(
            "%s - Ticket with id %s is closed, creating new ticket...",
            context.order_id,
            ticket_id,
        )
        return False

    def _are_customer_roles_deployed(self, context):
        try:
            # TODO implement new method to check roles using cloud orchestration API
            AWSClient(
                self._config,
                get_mpa_account_id(context.order),
                "",
            )
        except AWSError as error:
            logger.info("%s - Error - Customer role check failed: %s", context.order_id, error)
            return False
        return True
