import logging

import requests
from django.conf import settings
from mpt_extension_sdk.flows.pipeline import Pipeline, Step

from swo_aws_extension.constants import (
    HTTP_STATUS_OK,
    SWO_EXTENSION_MANAGEMENT_ROLE,
    AccountTypesEnum,
    PhasesEnum,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps import (
    AwaitInvitationLinksStep,
    SendInvitationLinksStep,
    SetupContextPurchaseTransferWithoutOrgStep,
    ValidatePurchaseTransferWithoutOrgStep,
)
from swo_aws_extension.parameters import get_account_type, get_phase
from swo_rql import RQLQuery

logger = logging.getLogger(__name__)


class CheckInvitationLinksStep(Step):
    """Check invitation links."""

    def __call__(self, client, context: PurchaseContext, next_step):
        """Execute step."""
        if get_phase(context.order) != PhasesEnum.CHECK_INVITATION_LINK:
            logger.info(
                "%s - Stop - Expecting phase '%s' got '%s'",
                context.order_id,
                PhasesEnum.CHECK_INVITATION_LINK.value,
                get_phase(context.order),
            )
            return
        next_step(client, context)


class AWSInvitationsProcessor:
    """Process AWS invitation."""

    def __init__(self, client, config):
        self.client = client
        self.config = config

    def get_querying_orders(self):
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
        while self.has_more_pages(page):
            try:
                response = self.client.get(f"{url}&limit={limit}&offset={offset}")
            except requests.RequestException:
                logger.exception("Cannot retrieve orders")
                return []

            if response.status_code == HTTP_STATUS_OK:
                page = response.json()
                orders.extend(page["data"])
            else:
                logger.warning("Order API error: %s %s", response.status_code, response.content)
                return []
            offset += limit

        return orders

    def has_more_pages(self, orders):
        """Are there more pages."""
        if not orders:
            return True
        pagination = orders["$meta"]["pagination"]
        return pagination["total"] > pagination["limit"] + pagination["offset"]

    def prepare_contexts(self) -> list[PurchaseContext]:
        """Prepare context."""
        return [PurchaseContext.from_order_data(order) for order in self.get_querying_orders()]

    # TODO: why? Step that returns pipeline, reverts all the logic
    def get_pipeline(self) -> Pipeline:
        """Returns pipeline."""
        return Pipeline(
            CheckInvitationLinksStep(),
            ValidatePurchaseTransferWithoutOrgStep(),
            SetupContextPurchaseTransferWithoutOrgStep(self.config, SWO_EXTENSION_MANAGEMENT_ROLE),
            SendInvitationLinksStep(),
            AwaitInvitationLinksStep(),
        )

    def is_processable(self, context: PurchaseContext) -> bool:
        """Is context processable."""
        return (
            context.is_purchase_order()
            and get_account_type(context.order) == AccountTypesEnum.EXISTING_ACCOUNT
            and context.is_type_transfer_without_organization()
            and get_phase(context.order) == PhasesEnum.CHECK_INVITATION_LINK
        )

    def process_aws_invitations(self):
        """Process AWS invitations."""
        for context in self.prepare_contexts():
            try:
                if not self.is_processable(context):
                    continue
                self.get_pipeline().run(self.client, context)
            except Exception:
                logger.exception()
