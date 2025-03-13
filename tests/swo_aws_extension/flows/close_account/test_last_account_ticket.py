
import pytest

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.flows.fulfillment.close_account.last_account_ticket import (
    build_service_request_for_close_account,
    create_ticket_on_close_account_criteria,
    crm_ticket_id_saver,
    is_last_active_account_criteria,
)
from swo_aws_extension.flows.order import CloseAccountContext


@pytest.fixture()
def aws_client(mocker):
    return mocker.Mock(spec=AWSClient)


@pytest.fixture()
def close_account_context(aws_client, order_close_account):
    return CloseAccountContext(
        order=order_close_account,
        aws_client=aws_client
    )


def test_create_close_account_ticket_criteria(aws_client):
    aws_client.list_accounts.return_value = [{'Status': 'ACTIVE'}, {'Status': 'ACTIVE'},
                                             {'Status': 'ACTIVE'}, ]
    assert is_last_active_account_criteria(aws_client) is False

    aws_client.list_accounts.return_value = [{'Status': 'ACTIVE'}, {'Status': 'ACTIVE'}]
    assert is_last_active_account_criteria(aws_client) is False

    aws_client.list_accounts.return_value = [{'Status': 'None'}, {'Status': 'None'},
                                             {'Status': 'ACTIVE'}, ]
    assert is_last_active_account_criteria(aws_client) is True

    aws_client.list_accounts.return_value = [{'Status': 'ACTIVE'}]
    assert is_last_active_account_criteria(aws_client) is True

    aws_client.list_accounts.return_value = []
    assert is_last_active_account_criteria(aws_client) is True

    aws_client.list_accounts.return_value = [{'Status': 'None'}, {'Status': 'None'}]
    assert is_last_active_account_criteria(aws_client) is True

    with pytest.raises(RuntimeError):
        is_last_active_account_criteria(None)


def test_create_ticket_on_close_account_criteria(mocker, close_account_context):
    is_last_active_account_criteria = mocker.patch(
        "swo_aws_extension.flows.fulfillment.close_account.last_account_ticket.is_last_active_account_criteria",
        return_value=True
    )
    get_crm_ticket_id = mocker.patch(
        "swo_aws_extension.flows.fulfillment.close_account.last_account_ticket.get_crm_ticket_id",
        return_value=False
    )
    result = create_ticket_on_close_account_criteria(close_account_context)
    assert result is True
    is_last_active_account_criteria.assert_called_once_with(close_account_context.aws_client)
    get_crm_ticket_id.assert_called_once_with(close_account_context.order)

    # Is not the last account
    is_last_active_account_criteria.return_value = False
    get_crm_ticket_id.return_value = None
    result = create_ticket_on_close_account_criteria(close_account_context)
    assert not result

    # Is the last account but already has a ticket
    is_last_active_account_criteria.return_value = True
    get_crm_ticket_id.return_value = "TicketID"
    result = create_ticket_on_close_account_criteria(close_account_context)
    assert not result


def test_build_service_request_for_close_account(
        mocker,
        close_account_context,
        fulfillment_parameters_factory
    ):
    result = build_service_request_for_close_account(close_account_context)
    expected_result = {
        'additionalInfo': 'additionalInfo',
         'externalUserEmail': 'test@example.com',
         'externalUsername': 'test@example.com',
         'globalacademicExtUserId': 'globalacademicExtUserId',
         'requester': 'Supplier.Portal',
         'serviceType': 'MarketPlaceServiceActivation',
         'subService': 'Service Activation',
         'summary': 'test',
         'title': 'test - Close MPA Account 123456789012'
    }
    assert result.__dict__ == expected_result
    close_account_context.order["parameters"]["fulfillment"]=fulfillment_parameters_factory(
        mpa_account_id=""
    )
    with pytest.raises(RuntimeError):
        build_service_request_for_close_account(close_account_context)

@pytest.fixture()
def close_account_order_with_crm_ticket(order_close_account, fulfillment_parameters_factory):
    order_close_account["parameters"]["fulfillment"] = fulfillment_parameters_factory(
        mpa_account_id="123"
    )
    return order_close_account


def test_crm_ticket_id_saver(mocker, close_account_context, close_account_order_with_crm_ticket):

    set_crm_ticket_id = mocker.patch(
        "swo_aws_extension.flows.fulfillment.close_account.last_account_ticket.set_crm_ticket_id",
        return_value=close_account_order_with_crm_ticket
    )
    update_order = mocker.patch(
        "swo_aws_extension.flows.fulfillment.close_account.last_account_ticket.update_order",
        return_value=close_account_order_with_crm_ticket
    )
    crm_ticket_id = "123"
    initial_order = close_account_context.order
    crm_ticket_id_saver(close_account_context.aws_client, close_account_context, crm_ticket_id)
    set_crm_ticket_id.assert_called_once_with(initial_order, crm_ticket_id)
    update_order.assert_called_once_with(
        close_account_context.aws_client,
        close_account_context.order_id,
        parameters=close_account_context.order["parameters"]
    )
