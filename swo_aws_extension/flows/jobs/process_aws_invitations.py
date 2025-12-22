import logging
from http import HTTPStatus

import requests
from django.conf import settings

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.aws.config import get_config
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.constants import (
    SWO_EXTENSION_MANAGEMENT_ROLE,
    OrderProcessingTemplateEnum,
    ResponsibilityTransferStatus,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.order_utils import switch_order_status_to_process_and_notify
from swo_aws_extension.notifications import TeamsNotificationManager
from swo_aws_extension.parameters import get_responsibility_transfer_id
from swo_aws_extension.swo.rql.query_builder import RQLQuery

logger = logging.getLogger(__name__)


class AWSInvitationsProcessor:
    """Process AWS invitation."""

    def __init__(self, client, config):
        self.client = client
        self.config = config

    def process_aws_invitations(self):
        """Process AWS invitations."""
        logger.info("Processing AWS pending invitations")
        for context in self._prepare_contexts():
            transfer_id = get_responsibility_transfer_id(context.order)
            context.aws_client = AWSClient(
                get_config(), context.pm_account_id, SWO_EXTENSION_MANAGEMENT_ROLE
            )

            try:
                transfer_details = context.aws_client.get_responsibility_transfer_details(
                    transfer_id=transfer_id
                )
            except AWSError as error:
                logger.info(
                    "%s - Error - Failed to get billing transfer invitation %s details: %s",
                    context.order_id,
                    transfer_id,
                    error,
                )
                TeamsNotificationManager().notify_one_time_error(
                    "Error processing AWS billing transfer invitations",
                    f"{context.order_id} - Error getting billing transfer invitation "
                    f"{transfer_id} details: {error!s}",
                )
                continue

            status = transfer_details.get("ResponsibilityTransfer", {}).get("Status")

            if status != ResponsibilityTransferStatus.REQUESTED:
                logger.info(
                    "%s - Action - Billing transfer invitation %s has changed status "
                    "to %s. Moving order to processing.",
                    context.order_id,
                    transfer_id,
                    status,
                )
                switch_order_status_to_process_and_notify(
                    self.client, context, OrderProcessingTemplateEnum.EXISTING_ACCOUNT
                )
                continue

            logger.info(
                "%s - Skip - Billing transfer invitation %s is still in REQUESTED status. "
                "Will check again later.",
                context.order_id,
                transfer_id,
            )

    # TODO: SDK candidate
    def _get_querying_orders(self):  # noqa: WPS210
        """Retrieve querying orders."""
        orders = []
        orders_for_product_ids = RQLQuery().agreement.product.id.in_(settings.MPT_PRODUCTS_IDS)
        orders_in_querying = RQLQuery(status="Querying")
        rql_query = orders_for_product_ids & orders_in_querying
        url = (
            f"/commerce/orders?{rql_query}&select=audit,parameters,lines,subscriptions,"
            f"subscriptions.lines,agreement,buyer&order=audit.created.at"
        )
        page = None
        limit = 10
        offset = 0
        while self._has_more_pages(page):
            try:
                response = self.client.get(f"{url}&limit={limit}&offset={offset}")
            except requests.RequestException:  # pragma: no cover
                logger.exception("Cannot retrieve orders")
                return []

            if response.status_code == HTTPStatus.OK:
                page = response.json()
                orders.extend(page.get("data") or [])
            else:  # pragma: no cover
                logger.warning("Order API error: %s %s", response.status_code, response.content)
                return []
            offset += limit

        return orders

    def _has_more_pages(self, orders):
        """Are there more pages."""
        if not orders:
            return True
        pagination = orders["$meta"]["pagination"]
        return pagination["total"] > pagination["limit"] + pagination["offset"]

    def _prepare_contexts(self) -> list[PurchaseContext]:
        """Prepare context."""
        return [PurchaseContext.from_order_data(order) for order in self._get_querying_orders()]
