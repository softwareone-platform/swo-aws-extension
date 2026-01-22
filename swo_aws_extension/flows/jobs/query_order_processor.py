import logging
from http import HTTPStatus
from typing import Any

import requests
from django.conf import settings
from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.config import Config
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.processors.processor import ProcessorChain
from swo_aws_extension.processors.querying.aws_billing_transfer_invitation import (
    AWSBillingTransferInvitationProcessor,
)
from swo_aws_extension.processors.querying.aws_channel_handshake import AWSChannelHandshakeProcessor
from swo_aws_extension.swo.rql.query_builder import RQLQuery

logger = logging.getLogger(__name__)


class PurchaseOrderQueryService:
    """Service to retrieve purchase orders in Querying state."""

    def __init__(self, client: MPTClient, config: Config):
        self.client = client
        self.config = config
        self.page_limit = 10

    def filter(self) -> RQLQuery:
        """Filter purchase orders in Querying state for MPT products."""
        orders_for_product_ids = RQLQuery().agreement.product.id.in_(settings.MPT_PRODUCTS_IDS)
        orders_in_querying = RQLQuery(status="Querying")
        order_is_purchase = RQLQuery(type="Purchase")
        return orders_for_product_ids & orders_in_querying & order_is_purchase

    def fetch_orders(self) -> list[dict[str, Any]]:
        """Retrieve orders matching filter criteria."""
        orders: list[dict[str, Any]] = []
        url = (
            f"/commerce/orders?{self.filter()}&select=audit,parameters,lines,subscriptions,"
            f"subscriptions.lines,agreement,buyer,authorization.externalIds&order=audit.created.at"
        )
        page = None
        offset = 0
        while self.has_more_pages(page):
            try:
                response = self.client.get(f"{url}&limit={self.page_limit}&offset={offset}")
            except requests.RequestException:  # pragma: no cover
                logger.exception("Cannot retrieve orders")
                return []

            if response.status_code == HTTPStatus.OK:
                page = response.json()
                orders.extend(page.get("data") or [])
            else:  # pragma: no cover
                logger.warning("Order API error: %s %s", response.status_code, response.content)
                return []
            offset += self.page_limit

        return orders

    def get_orders_as_context(self) -> list[PurchaseContext]:
        """Retrieve orders and setup as PurchaseContext."""
        return [PurchaseContext.from_order_data(order) for order in self.fetch_orders()]

    def has_more_pages(self, orders):
        """Are there more pages."""
        if not orders:
            return True
        pagination = orders["$meta"]["pagination"]
        return pagination["total"] > pagination["limit"] + pagination["offset"]


def process_query_orders(client, config):
    """Iterates orders contexts and processes each in the processor chain."""
    query_service = PurchaseOrderQueryService(client, config)
    query_processor_chain = ProcessorChain([
        AWSBillingTransferInvitationProcessor(client),
        AWSChannelHandshakeProcessor(client, config),
    ])
    for context in query_service.get_orders_as_context():
        try:
            query_processor_chain.process(context)
        except Exception:
            logger.exception("Error processing order in Querying state context")
