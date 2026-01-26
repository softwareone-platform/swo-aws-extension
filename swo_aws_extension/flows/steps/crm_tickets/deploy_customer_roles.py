import logging
from typing import override

from swo_aws_extension.constants import CRM_TICKET_RESOLVED_STATE, PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.crm_tickets.base import BaseCRMTicketStep
from swo_aws_extension.flows.steps.crm_tickets.templates.deploy_roles import DEPLOY_ROLES_TEMPLATE
from swo_aws_extension.flows.steps.errors import SkipStepError, UnexpectedStopError
from swo_aws_extension.parameters import (
    get_crm_customer_role_ticket_id,
    get_formatted_technical_contact,
    get_mpa_account_id,
    set_crm_customer_role_ticket_id,
)
from swo_aws_extension.swo.cloud_orchestrator.client import CloudOrchestratorClient
from swo_aws_extension.swo.cloud_orchestrator.errors import CloudOrchestratorError
from swo_aws_extension.swo.crm_service.client import get_service_client

logger = logging.getLogger(__name__)


class CRMTicketDeployCustomerRoles(BaseCRMTicketStep):
    """CRM Ticket Deploy Customer Roles Step."""

    ticket_name = "Deploy Customer Roles"
    template = DEPLOY_ROLES_TEMPLATE

    @override
    def pre_step(self, context: PurchaseContext) -> None:
        if context.phase != PhasesEnum.CHECK_CUSTOMER_ROLES:
            raise SkipStepError(
                f"{context.order_id} - Next - Current phase is '{context.phase}', skipping "
                f"create Deploy Customer Roles ticket"
            )
        if self._has_open_ticket(context):
            raise SkipStepError(
                f"{context.order_id} - Next - CRM Deploy Customer Roles ticket is already created,"
                f" skipping step"
            )
        if self._are_customer_roles_deployed(context):
            raise SkipStepError(
                f"{context.order_id} - Next - Customer roles are already deployed, skipping "
                f"Deploy Customer Roles ticket creation"
            )

    @override
    def _build_summary(self, context: PurchaseContext) -> str:
        contact = get_formatted_technical_contact(context.order)
        return self.template.summary.format(
            customer_name=context.buyer.get("name"),
            buyer_id=context.buyer.get("id"),
            buyer_external_id=context.buyer.get("externalIds", {}).get("erpCustomer", ""),
            order_id=context.order_id,
            master_payer_id=get_mpa_account_id(context.order),
            technical_contact_name=contact["name"],
            technical_contact_email=contact["email"],
            technical_contact_phone=contact["phone"],
        )

    @override
    def _set_ticket_id(self, order: dict, ticket_id: str) -> dict:
        return set_crm_customer_role_ticket_id(order, ticket_id)

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
        if not context.bootstrap_roles_status:
            co_client = CloudOrchestratorClient(self._config)
            mpa_account_id = get_mpa_account_id(context.order)
            try:
                bootstrap_roles_status = co_client.get_bootstrap_role_status(mpa_account_id)
            except CloudOrchestratorError as error:
                raise UnexpectedStopError(
                    "Error checking customer roles", f"Error details: {error}"
                ) from error
            context.bootstrap_roles_status = bootstrap_roles_status

        return context.bootstrap_roles_status["deployed"]
