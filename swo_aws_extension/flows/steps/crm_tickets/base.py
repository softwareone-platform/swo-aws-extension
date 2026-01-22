import logging
from abc import ABC, abstractmethod
from typing import override

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.aws.config import Config
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.crm_tickets.templates.models import CRMTicketTemplate
from swo_aws_extension.flows.steps.errors import UnexpectedStopError
from swo_aws_extension.swo.crm_service.client import ServiceRequest, get_service_client
from swo_aws_extension.swo.crm_service.errors import CRMError

logger = logging.getLogger(__name__)


class BaseCRMTicketStep(BasePhaseStep, ABC):
    """Abstract base class for CRM ticket creation steps."""

    ticket_name: str
    template: CRMTicketTemplate

    def __init__(self, config: Config) -> None:
        """Initialize the CRM ticket step."""
        self._config = config

    @override
    def process(self, client: MPTClient, context: PurchaseContext) -> None:
        crm_client = get_service_client()
        service_request = ServiceRequest(
            additional_info=self.template.additional_info,
            summary=self._build_summary(context),
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

        ticket_id = response.get("id")
        if ticket_id:
            context.order = self._set_ticket_id(context.order, ticket_id)
            logger.info(
                "%s - %s ticket created with ID %s", context.order_id, self.ticket_name, ticket_id
            )
        else:
            logger.info("%s - No ticket ID returned from CRM", context.order_id)

    @override
    def post_step(self, client: MPTClient, context: PurchaseContext) -> None:
        context.order = update_order(
            client, context.order_id, parameters=context.order["parameters"]
        )

    @abstractmethod
    def _build_summary(self, context: PurchaseContext) -> str:
        raise NotImplementedError

    @abstractmethod
    def _set_ticket_id(self, order: dict, ticket_id: str) -> dict:
        raise NotImplementedError
