from typing import override

from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.crm_tickets.base import BaseCRMTicketStep
from swo_aws_extension.flows.steps.crm_tickets.templates.new_account import NEW_ACCOUNT_TEMPLATE
from swo_aws_extension.flows.steps.errors import SkipStepError
from swo_aws_extension.parameters import (
    get_crm_new_account_ticket_id,
    get_formatted_supplementary_services,
    get_formatted_technical_contact,
    get_order_account_email,
    get_order_account_name,
    get_support_type,
    set_crm_new_account_ticket_id,
)


class CRMTicketNewAccount(BaseCRMTicketStep):
    """CRM Ticket New Account Step."""

    ticket_name = "New Account"
    template = NEW_ACCOUNT_TEMPLATE

    @override
    def pre_step(self, context: PurchaseContext) -> None:
        if context.phase != PhasesEnum.CREATE_NEW_AWS_ENVIRONMENT:
            raise SkipStepError(
                f"{context.order_id} - Next - Current phase is '{context.phase}', skipping "
                f"create new account ticket"
            )
        if get_crm_new_account_ticket_id(context.order):
            raise SkipStepError(
                f"{context.order_id} - Next - CRM New Account Ticket is already created,"
                f" skipping step"
            )

    @override
    def _build_summary(self, context: PurchaseContext) -> str:
        contact = get_formatted_technical_contact(context.order)
        return self.template.summary.format(
            customer_name=context.buyer.get("name"),
            buyer_id=context.buyer.get("id"),
            buyer_external_id=context.buyer.get("externalIds", {}).get("erpCustomer", ""),
            order_id=context.order_id,
            order_account_name=get_order_account_name(context.order),
            order_account_email=get_order_account_email(context.order),
            technical_contact_name=contact["name"],
            technical_contact_email=contact["email"],
            technical_contact_phone=contact["phone"],
            support_type=get_support_type(context.order),
            supplementary_services=get_formatted_supplementary_services(context.order),
        )

    @override
    def _set_ticket_id(self, order: dict, ticket_id: str) -> dict:
        return set_crm_new_account_ticket_id(order, ticket_id)
