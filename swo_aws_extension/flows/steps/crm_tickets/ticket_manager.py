import logging

from swo_aws_extension.config import Config
from swo_aws_extension.constants import CRM_TICKET_RESOLVED_STATE
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.crm_tickets.templates.models import CRMTicketTemplate
from swo_aws_extension.flows.steps.errors import UnexpectedStopError
from swo_aws_extension.parameters import get_crm_customer_role_ticket_id
from swo_aws_extension.swo.crm_service.client import ServiceRequest, get_service_client
from swo_aws_extension.swo.crm_service.errors import CRMError

logger = logging.getLogger(__name__)


class TicketManager:
    """Ticket manager class."""

    def __init__(self, config: Config, ticket_name: str, template: CRMTicketTemplate):
        self.config = config
        self.ticket_name = ticket_name
        self.template = template

    def create_new_ticket(self, context, summary):
        """Create a new ticket.

        Args:
            context: The context of the order.
            summary: The summary of the ticket.

        Returns:
            The id of the new ticket.
        """
        crm_client = get_service_client()
        service_request = ServiceRequest(
            additional_info=self.template.additional_info,
            summary=summary,
            title=self.template.title,
        )
        try:
            response = crm_client.create_service_request(context.order_id, service_request)
        except CRMError as error:
            logger.info(
                "%s - Failed to create %s ticket: %s", context.order_id, self.ticket_name, error
            )
            raise UnexpectedStopError(
                f"Error creating {self.ticket_name} ticket", f"Error details: {error}"
            ) from error

        return response.get("id")

    def has_open_ticket(self, context: PurchaseContext) -> bool:
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
