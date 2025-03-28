import logging
from typing import Callable

from swo.mpt.client import MPTClient
from swo.mpt.client.mpt import update_order
from swo.mpt.extensions.flows.pipeline import NextStep, Step

from swo_aws_extension.constants import CRM_TICKET_COMPLETED_STATE
from swo_aws_extension.crm_service_client.config import get_service_client
from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.parameters import get_crm_ticket_id, set_crm_ticket_id
from swo_crm_service_client import ServiceRequest

logger = logging.getLogger(__name__)


class AwaitCRMTicketStatusStep(Step):
    def __init__(
        self,
        get_ticket_id: callable(InitialAWSContext),
        target_status=None,
        skip_if_no_ticket=True,
    ):
        """
        Await for a CRM ticket to reach any of the target status before proceeding.
        :param get_ticket_id: Callable[[CloseAccountContext], str|None] - Get ticket ID from context
        :param target_status: Optional[str | List[str]]
            Example: ["Completed", "Closed"] Default: [CRM_TICKET_COMPLETED_STATE]
        :param skip_if_no_ticket: bool - Skip if no ticket ID is found

        :raise ValueError: If ticket ID is required and not found
        """
        self.get_ticket_id = get_ticket_id
        target_status = target_status or [CRM_TICKET_COMPLETED_STATE]
        if not isinstance(target_status, list):
            target_status = [target_status]
        self.target_status = target_status
        self.skip_if_no_ticket = skip_if_no_ticket

    def __call__(
        self,
        client: MPTClient,
        context: InitialAWSContext,
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
        if ticket["state"] not in self.target_status:
            logger.info(
                f"{context.order_id} - Stopping - Awaiting for ticket_id={ticket_id} "
                f"to move from state={ticket['state']} to any of {self.target_status}"
            )
            return
        next_step(client, context)


class CreateServiceRequestStep(Step):
    def __init__(
        self,
        service_request_factory: Callable[[InitialAWSContext], ServiceRequest],
        ticket_id_saver: Callable[[MPTClient, InitialAWSContext, str], None],
        criteria: Callable[[InitialAWSContext], bool] = None,
    ):
        self.service_request_factory = service_request_factory
        self.ticket_id_saver = ticket_id_saver
        self.criteria = criteria or (lambda context: True)

    def meets_criteria(self, context):
        return self.criteria(context)

    def __call__(
        self,
        client: MPTClient,
        context: InitialAWSContext,
        next_step: NextStep,
    ) -> None:
        if not self.meets_criteria(context):
            logger.info(
                f"{context.order_id} - Skipping - Criteria not met to Create a Service ticket."
            )
            next_step(client, context)
            return
        service_request = self.service_request_factory(context)
        crm_client = get_service_client()
        response = crm_client.create_service_request(context.order_id, service_request)
        ticket_id = response.get("id", None)
        self.ticket_id_saver(client, context, ticket_id)
        logger.info(
            f"{context.order_id} - Action - Created service request with ticket_id={ticket_id}"
        )
        next_step(client, context)


class CreateMPADecomissionServiceRequestStep(CreateServiceRequestStep):
    def is_only_mpa_account_in_organization(self, aws_client) -> bool:
        if aws_client is None:
            raise RuntimeError(
                "IsLastAccountActiveCriteria requires an AWSClient "
                "instance set in context.aws_client"
            )
        accounts = aws_client.list_accounts()
        active_accounts = list(filter(lambda a: a.get("Status") == "ACTIVE", accounts))
        num_active_accounts = len(active_accounts)
        return num_active_accounts <= 1

    def should_create_ticket_criteria(self, context: InitialAWSContext) -> bool:
        """
        A Service Request to close the account has to be sent to service team when only one
        active account is left (the Master Payer Account)

        :param context:
        :return:
        """
        return self.is_only_mpa_account_in_organization(
            context.aws_client
        ) and not get_crm_ticket_id(context.order)

    def build_service_request_for_close_account(
        self, context: InitialAWSContext
    ) -> ServiceRequest:
        if not context.mpa_account:
            raise RuntimeError(
                "Unable to create a service request ticket for an order missing an "
                "MPA account in the fulfillment parameters"
            )

        return ServiceRequest(
            external_user_email="test@example.com",
            external_username="test@example.com",
            requester="Supplier.Portal",
            sub_service="Service Activation",
            global_academic_ext_user_id="globalacademicExtUserId",
            additional_info="additionalInfo",
            summary="test",
            title=f"test - Close MPA Account {context.mpa_account}",
            service_type="MarketPlaceServiceActivation",
        )

    def save_ticket(self, client, context, crm_ticket_id):
        if not crm_ticket_id:
            raise ValueError("Updating crm service ticket id - Ticket id is required.")
        context.order = set_crm_ticket_id(context.order, crm_ticket_id)
        update_order(client, context.order_id, parameters=context.order["parameters"])

    def __init__(self):
        super().__init__(
            service_request_factory=self.build_service_request_for_close_account,
            ticket_id_saver=self.save_ticket,
            criteria=self.should_create_ticket_criteria,
        )


class AwaitMPADecommissionServiceRequestTicketCompletionStep(AwaitCRMTicketStatusStep):
    def get_crm_ticket(self, context: InitialAWSContext):
        return get_crm_ticket_id(context.order)

    def __init__(self):
        super().__init__(
            get_ticket_id=self.get_crm_ticket,
            target_status=CRM_TICKET_COMPLETED_STATE,
            skip_if_no_ticket=True,
        )
