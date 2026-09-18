from typing import override

from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.crm_tickets.base import BaseCRMTicketStep
from swo_aws_extension.flows.steps.crm_tickets.templates.migration import MIGRATION_TEMPLATE
from swo_aws_extension.flows.steps.errors import SkipStepError
from swo_aws_extension.parameters import (
    get_cco_contract_number,
    get_channel_handshake_approval_status,
    get_crm_migration_ticket_id,
    get_formatted_technical_contact,
    get_mpa_account_id,
    get_support_type,
    set_crm_migration_ticket_id,
)


class CRMTicketMigration(BaseCRMTicketStep):
    """
    CRM ticket step for migrated AWS customers.

    Runs once the billing transfer and the channel handshake are settled, in the
    createSubscription phase of the migration pipeline. The ticket id is stored in the
    crmMigrationTicketId fulfillment parameter, so the ticket is created only once.
    """

    ticket_name = "Migration"
    template = MIGRATION_TEMPLATE

    @override
    def pre_step(self, context: PurchaseContext) -> None:
        if context.phase != PhasesEnum.CREATE_SUBSCRIPTION:
            raise SkipStepError(
                f"{context.order_id} - Next - Current phase is '{context.phase}', skipping "
                f"create migration ticket"
            )
        if get_crm_migration_ticket_id(context.order):
            raise SkipStepError(
                f"{context.order_id} - Next - CRM Migration Ticket is already created,"
                f" skipping step"
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
            agreement_id=context.agreement.get("id", ""),
            master_payer_id=get_mpa_account_id(context.order),
            cco_contract_number=get_cco_contract_number(context.order),
            handshake_approved=get_channel_handshake_approval_status(context.order).capitalize(),
            technical_contact_name=contact["name"],
            technical_contact_email=contact["email"],
            technical_contact_phone=contact["phone"],
            support_type=get_support_type(context.order),
        )

    @override
    def _set_ticket_id(self, order: dict, ticket_id: str) -> dict:
        return set_crm_migration_ticket_id(order, ticket_id)
