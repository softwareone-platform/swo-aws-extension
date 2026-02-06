import logging
from abc import ABC, abstractmethod
from typing import override

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.config import Config
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.crm_tickets.templates.models import CRMTicketTemplate
from swo_aws_extension.flows.steps.crm_tickets.ticket_manager import TicketManager

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
        ticket_id = TicketManager(
            config=self._config, ticket_name=self.ticket_name, template=self.template
        ).create_new_ticket(context, self._build_summary(context))

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
