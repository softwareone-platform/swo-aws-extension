import datetime as dt
import logging
from typing import override

from dateutil.relativedelta import relativedelta

from swo_aws_extension.constants import ChannelHandshakeDeployed, ExpirationPeriodEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.crm_tickets.base import BaseCRMTicketStep
from swo_aws_extension.flows.steps.crm_tickets.templates.terminate_order import (
    ORDER_TERMINATION_TEMPLATE,
)
from swo_aws_extension.flows.steps.errors import SkipStepError
from swo_aws_extension.parameters import (
    get_channel_handshake_approval_status,
    get_crm_terminate_order_ticket_id,
    get_formatted_supplementary_services,
    get_formatted_technical_contact,
    get_mpa_account_id,
    get_support_type,
    set_crm_terminate_order_ticket_id,
)

logger = logging.getLogger(__name__)


class CRMTicketTerminateOrder(BaseCRMTicketStep):
    """CRM Ticket Terminate Order Step."""

    ticket_name = "Terminate Order"
    template = ORDER_TERMINATION_TEMPLATE

    @override
    def pre_step(self, context: PurchaseContext) -> None:
        if get_crm_terminate_order_ticket_id(context.order):
            raise SkipStepError(
                f"{context.order_id} - Next - CRM Terminate Order Ticket is already created,"
                f" skipping step"
            )

    @override
    def _build_summary(self, context: PurchaseContext) -> str:
        contact = get_formatted_technical_contact(context.order)
        handshake_approved = (
            get_channel_handshake_approval_status(context.order) == ChannelHandshakeDeployed.YES
        )
        return self.template.summary.format(
            end_date=self._get_last_day_of_the_next_month_timestamp(
                handshake_approved=handshake_approved
            ),
            customer_name=context.buyer.get("name"),
            buyer_id=context.buyer.get("id"),
            buyer_external_id=context.buyer.get("externalIds", {}).get("erpCustomer", ""),
            order_id=context.order_id,
            master_payer_id=get_mpa_account_id(context.order),
            technical_contact_name=contact["name"],
            technical_contact_email=contact["email"],
            technical_contact_phone=contact["phone"],
            support_type=get_support_type(context.order),
            supplementary_services=get_formatted_supplementary_services(context.order),
        )

    @override
    def _set_ticket_id(self, order: dict, ticket_id: str) -> dict:
        return set_crm_terminate_order_ticket_id(order, ticket_id)

    def _get_last_day_of_the_next_month_timestamp(self, *, handshake_approved: bool) -> str:
        now = dt.datetime.now(dt.UTC)
        delta = (
            relativedelta(months=ExpirationPeriodEnum.NEXT_MONTH)
            if handshake_approved
            else relativedelta(months=ExpirationPeriodEnum.CURRENT_MONTH)
        )

        first_day_month_after_next = (now + delta).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        last_day = first_day_month_after_next - dt.timedelta(milliseconds=1)
        return last_day.strftime("%Y-%m-%d %H:%M:%S")
