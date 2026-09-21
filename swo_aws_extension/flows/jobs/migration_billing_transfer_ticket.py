import logging
from typing import Any

from mpt_api_client.exceptions import MPTError
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_agreement

from swo_aws_extension.airtable.models import AccountMigrationRecord
from swo_aws_extension.constants import FulfillmentParametersEnum, ParamPhasesEnum
from swo_aws_extension.flows.steps.crm_tickets.templates.billing_transfer_start import (
    BILLING_TRANSFER_START_TEMPLATE,
)
from swo_aws_extension.parameters import get_crm_migration_ticket_id
from swo_aws_extension.swo.crm_service.client import ServiceRequest, get_service_client

logger = logging.getLogger(__name__)

NOT_AVAILABLE = "N/A"


def get_stored_ticket_id(order: dict[str, Any]) -> str | None:
    """Return the billing transfer start ticket id stored in the order agreement, if any."""
    agreement = order.get("agreement") or {}
    if not agreement.get("parameters"):
        return None
    return get_crm_migration_ticket_id(agreement)


def build_ticket_request(
    record: AccountMigrationRecord, order: dict[str, Any], start_date: str
) -> ServiceRequest:
    """Build the MCoE ticket that notifies the billing transfer start of a migrated account."""
    buyer = order.get("buyer") or {}
    seller = order.get("seller") or {}
    summary = BILLING_TRANSFER_START_TEMPLATE.summary.format(
        customer_name=buyer.get("name", ""),
        buyer_id=buyer.get("id", record.swo_buyer),
        buyer_external_id=buyer.get("externalIds", {}).get("erpCustomer", ""),
        seller_country=(seller.get("address") or {}).get("country", ""),
        order_id=record.mpt_order_id,
        agreement_id=(order.get("agreement") or {}).get("id", ""),
        master_payer_id=record.masterpayer,
        cco_contract_number=record.mpt_cco,
        billing_transfer_start_date=start_date,
        technical_contact_name=record.technical_contact_name or NOT_AVAILABLE,
        technical_contact_email=record.technical_contact_email or NOT_AVAILABLE,
        technical_contact_phone=record.technical_phone or NOT_AVAILABLE,
        support_type=record.aws_support_type,
    )
    return ServiceRequest(
        additional_info=BILLING_TRANSFER_START_TEMPLATE.additional_info,
        summary=summary,
        title=BILLING_TRANSFER_START_TEMPLATE.title,
    )


def create_ticket(record: AccountMigrationRecord, order: dict[str, Any], start_date: str) -> str:
    """
    Create the billing transfer start ticket for the MCoE team and return its id.

    Raises:
        CRMError: When the ticket cannot be created.
    """
    order_id = record.mpt_order_id
    service_request = build_ticket_request(record, order, start_date)
    response = get_service_client().create_service_request(order_id, service_request)
    ticket_id = str(response.get("id"))
    logger.info("%s - Billing transfer start ticket created: %s", order_id, ticket_id)
    return ticket_id


def store_ticket_id(mpt_client: MPTClient, order: dict[str, Any], ticket_id: str) -> bool:
    """
    Store the ticket id in the agreement so a retried row does not get a second ticket.

    Returns whether the id was stored; a Marketplace error is logged and reported as False.
    """
    order_id = order.get("id")
    agreement_id = (order.get("agreement") or {}).get("id")
    agreement_parameters = {
        ParamPhasesEnum.FULFILLMENT.value: [
            {
                "externalId": FulfillmentParametersEnum.CRM_MIGRATION_TICKET_ID.value,
                "value": ticket_id,
            }
        ]
    }
    try:
        update_agreement(mpt_client, agreement_id, parameters=agreement_parameters)
    except MPTError as error:
        logger.warning(
            "%s - Error - Ticket %s created but not stored in the agreement: %s",
            order_id,
            ticket_id,
            error,
        )
        return False
    return True
