from typing import override

from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.crm_tickets.base import BaseCRMTicketStep
from swo_aws_extension.flows.steps.crm_tickets.templates.onboard_services import (
    ONBOARD_SERVICES_TEMPLATE,
)
from swo_aws_extension.flows.steps.errors import SkipStepError
from swo_aws_extension.parameters import (
    get_crm_onboard_ticket_id,
    get_formatted_supplementary_services,
    get_formatted_technical_contact,
    get_mpa_account_id,
    get_support_type,
    set_crm_onboard_ticket_id,
)


class CRMTicketOnboardServices(BaseCRMTicketStep):
    """CRM Ticket Onboard Services Step."""

    ticket_name = "Onboard Services"
    template = ONBOARD_SERVICES_TEMPLATE

    @override
    def pre_step(self, context: PurchaseContext) -> None:
        if context.phase != PhasesEnum.ONBOARD_SERVICES:
            raise SkipStepError(
                f"{context.order_id} - Next - Current phase is '{context.phase}', skipping "
                f"create onboard services ticket"
            )
        if get_crm_onboard_ticket_id(context.order):
            raise SkipStepError(
                f"{context.order_id} - Next - CRM Onboard Services Ticket is already created,"
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
            master_payer_id=get_mpa_account_id(context.order),
            technical_contact_name=contact["name"],
            technical_contact_email=contact["email"],
            technical_contact_phone=contact["phone"],
            support_type=get_support_type(context.order),
            supplementary_services=get_formatted_supplementary_services(context.order),
        )

    @override
    def _set_ticket_id(self, order: dict, ticket_id: str) -> dict:
        return set_crm_onboard_ticket_id(order, ticket_id)
