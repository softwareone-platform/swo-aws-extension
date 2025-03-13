from swo.mpt.client import MPTClient
from swo.mpt.extensions.flows.pipeline import NextStep, Step

from swo_aws_extension.crm_service_client.config import get_service_client
from swo_aws_extension.flows.order import CloseAccountContext


class CreateServiceRequestStep(Step):
    def __init__(self,
                 service_request_factory,
                 ticket_id_saver,
                 criteria=None,
            ):
        self.service_request_factory = service_request_factory
        self.ticket_id_saver = ticket_id_saver
        self.criteria = criteria or (lambda context: True)

    def meets_criteria(self, context):
        return self.criteria(context)

    def __call__(
            self,
            client: MPTClient,
            context: CloseAccountContext,
            next_step: NextStep,
    ) -> None:
        if not self.meets_criteria(context):
            next_step(client, context)
            return
        service_request = self.service_request_factory(context)
        crm_client = get_service_client()
        response=crm_client.create_service_request(context.order_id, service_request)
        ticket_id = response.get("id", None)
        if not ticket_id:
            raise ValueError("Response from CRM service did not contain a ticket ID")
        self.ticket_id_saver(client, context, ticket_id)
        next_step(client, context)
