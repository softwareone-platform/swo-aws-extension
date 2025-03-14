from swo.mpt.client.mpt import update_order

from swo_aws_extension.flows.order import CloseAccountContext
from swo_aws_extension.parameters import (
    get_crm_ticket_id,
    get_mpa_account_id,
    set_crm_ticket_id,
)
from swo_crm_service_client.client import ServiceRequest


def is_last_active_account_criteria(aws_client):
    if aws_client is None:
        raise RuntimeError(
            "IsLastAccountActiveCriteria requires an AWSClient "
            "instance set in context.aws_client"
        )
    accounts = aws_client.list_accounts()
    active_accounts = list(filter(lambda a: a.get('Status') == 'ACTIVE', accounts))
    num_active_accounts = len(active_accounts)
    return num_active_accounts <= 1


def create_ticket_on_close_account_criteria(context: CloseAccountContext):
    """
    A Service Request to close the account has to be sent to service team when only one
    active account is left (the Master Payer Account)

    :param context:
    :return:
    """
    return (
            is_last_active_account_criteria(context.aws_client)
            and not get_crm_ticket_id(context.order)
    )


def build_service_request_for_close_account(context: CloseAccountContext):
    mpa_account = get_mpa_account_id(context.order)
    if mpa_account is None:
        raise RuntimeError("MPA Account ID is not set in order parameters")

    return ServiceRequest(
        externalUserEmail="user@example.com",
        externalUsername="username",
        requester="requester",
        subService="subService",
        globalacademicExtUserId="globalacademicExtUserId",
        additionalInfo="additionalInfo",
        summary="summary",
        title=f"Close MPA Account {mpa_account}",
        serviceType="serviceType",
    )


def crm_ticket_id_saver(client, context, crm_ticket_id):
    context.order = set_crm_ticket_id(context.order, crm_ticket_id)
    update_order(client, context.order_id, parameters=context.order["parameters"])
