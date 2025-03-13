from swo.mpt.client import MPTClient
from swo.mpt.extensions.flows.pipeline import NextStep, Step

from swo_aws_extension.crm_service_client.config import get_service_client
from swo_aws_extension.flows.order import CloseAccountContext


class AwaitCRMTicketStatusStep(Step):

    def __init__(
        self,
        get_ticket_id: callable(CloseAccountContext),
        target_status = None,
        skip_if_no_ticket = True,
    ):
        """
        Await for a CRM ticket to reach any of the target status before proceeding.
        :param get_ticket_id: Callable[[CloseAccountContext], str|None] - Get ticket ID from context
        :param target_status: Optional[str | List[str]]
            Example: ["completed", "closed"] Default: ["completed"]
        :param skip_if_no_ticket: bool - Skip if no ticket ID is found

        :raise ValueError: If ticket ID is required and not found
        """
        self.get_ticket_id = get_ticket_id
        target_status = target_status or ["completed"]
        if not isinstance(target_status, list):
            target_status = [target_status]
        self.target_status = target_status
        self.skip_if_no_ticket = skip_if_no_ticket

    def __call__(
        self,
        client: MPTClient,
        context: CloseAccountContext,
        next_step: NextStep,
    ) -> None:
        ticket_id = self.get_ticket_id(context)
        if not ticket_id and not self.skip_if_no_ticket:
            raise ValueError("Ticket ID is required.")
        if not ticket_id:
            next_step(client, context)
            return
        crm_service_client = get_service_client()
        ticket = crm_service_client.get_service_requests(context.order_id, ticket_id)
        if ticket["status"] not in self.target_status:
            return
        next_step(client, context)

