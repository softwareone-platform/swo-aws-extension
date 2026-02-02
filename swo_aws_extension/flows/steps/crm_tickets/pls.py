from typing import override

from swo_aws_extension.constants import SupportTypesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.crm_tickets.base import BaseCRMTicketStep
from swo_aws_extension.flows.steps.crm_tickets.templates.pls import PLS_TEMPLATE
from swo_aws_extension.flows.steps.errors import SkipStepError
from swo_aws_extension.parameters import (
    get_channel_handshake_approval_status,
    get_crm_pls_ticket_id,
    get_customer_roles_deployed,
    get_formatted_supplementary_services,
    get_formatted_technical_contact,
    get_mpa_account_id,
    get_support_type,
    set_crm_pls_ticket_id,
)


class CRMTicketPLS(BaseCRMTicketStep):
    """CRM Ticket PLS Step."""

    ticket_name = "PLS"
    template = PLS_TEMPLATE

    @override
    def pre_step(self, context: PurchaseContext) -> None:
        support_type = get_support_type(context.order)
        if support_type != SupportTypesEnum.PARTNER_LED_SUPPORT:
            raise SkipStepError(
                f"{context.order_id} - Next - Support type is '{support_type}', skipping create a "
                f"ticket as it is not {SupportTypesEnum.PARTNER_LED_SUPPORT}"
            )
        if get_crm_pls_ticket_id(context.order):
            raise SkipStepError(
                f"{context.order_id} - Next - CRM PLS Ticket is already created, skipping step"
            )

    @override
    def _build_summary(self, context: PurchaseContext) -> str:
        contact = get_formatted_technical_contact(context.order)
        return self.template.summary.format(
            customer_name=context.buyer.get("name"),
            buyer_id=context.buyer.get("id"),
            buyer_external_id=context.buyer.get("externalIds", {}).get("erpCustomer", ""),
            seller_country=context.seller.get("address", {}).get("country", ""),
            pm_account_id=context.pm_account_id,
            order_id=context.order_id,
            master_payer_id=get_mpa_account_id(context.order),
            technical_contact_name=contact["name"],
            technical_contact_email=contact["email"],
            technical_contact_phone=contact["phone"],
            support_type=get_support_type(context.order),
            supplementary_services=get_formatted_supplementary_services(context.order),
            handshake_approved=get_channel_handshake_approval_status(context.order).capitalize(),
            customer_roles_deployed=get_customer_roles_deployed(context.order).capitalize(),
        )

    @override
    def _set_ticket_id(self, order: dict, ticket_id: str) -> dict:
        return set_crm_pls_ticket_id(order, ticket_id)
