import logging

import requests
from django.conf import settings
from mpt_extension_sdk.core.utils import setup_client
from mpt_extension_sdk.flows.pipeline import Pipeline, Step

from swo_aws_extension.constants import SWO_EXTENSION_MANAGEMENT_ROLE, AccountTypesEnum, PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps import (
    AwaitInvitationLinksStep,
    SendInvitationLinksStep,
    SetupContextPurchaseTransferWithoutOrganizationStep,
    ValidatePurchaseTransferWithoutOrganizationStep,
)
from swo_aws_extension.parameters import get_account_type, get_phase
from swo_rql import RQLQuery

logger = logging.getLogger(__name__)


class CheckInvitationLinksStep(Step):
    def __call__(self, client, context: PurchaseContext, next_step):
        if get_phase(context.order) != PhasesEnum.CHECK_INVITATION_LINK:
            logger.info(
                f"{context.order_id} - Stop - "
                f"Expecting phase '{PhasesEnum.CHECK_INVITATION_LINK}'"
                f" got '{get_phase(context.order)}'"
            )
            return
        next_step(client, context)


class AWSInvitationsProcessor:
    def __init__(self, config):
        self.client = setup_client()
        self.config = config

    def get_querying_orders(self):
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

            if response.status_code == 200:
                page = response.json()
                orders.extend(page["data"])
            else:
                logger.warning(f"Order API error: {response.status_code} {response.content}")
                return []
            offset += limit

        return orders

    def has_more_pages(self, orders):
        if not orders:
            return True
        pagination = orders["$meta"]["pagination"]
        return pagination["total"] > pagination["limit"] + pagination["offset"]

    def prepare_contexts(self) -> list[PurchaseContext]:
        contexts = []
        for o in self.get_querying_orders():
            contexts.append(PurchaseContext.from_order_data(o))

        return contexts

    def get_pipeline(self) -> Pipeline:
        return Pipeline(
            CheckInvitationLinksStep(),
            ValidatePurchaseTransferWithoutOrganizationStep(),
            SetupContextPurchaseTransferWithoutOrganizationStep(
                self.config, SWO_EXTENSION_MANAGEMENT_ROLE
            ),
            SendInvitationLinksStep(),
            AwaitInvitationLinksStep(),
        )

    def is_processable(self, context: PurchaseContext) -> bool:
        return (
            context.is_purchase_order()
            and get_account_type(context.order) == AccountTypesEnum.EXISTING_ACCOUNT
            and context.is_type_transfer_without_organization()
            and get_phase(context.order) == PhasesEnum.CHECK_INVITATION_LINK
        )

    def process_aws_invitations(self):
        """
        Process AWS invitations.
        """
        client = self.client

        contexts = self.prepare_contexts()
        pipeline = self.get_pipeline()
        for context in contexts:
            try:
                if not self.is_processable(context):
                    continue
                pipeline.run(client, context)
            except Exception as e:
                logger.exception(e)
