from unittest.mock import call

import pytest

from swo_aws_extension.constants import CRM_TICKET_COMPLETED_STATE
from swo_aws_extension.flows.fulfillment.pipelines import (
    close_account as close_account_pipeline,
)
from swo_aws_extension.flows.order import CloseAccountContext
from swo_aws_extension.parameters import set_crm_ticket_id
from swo_crm_service_client.client import CRMServiceClient


@pytest.fixture()
def service_client(mocker):
    return mocker.Mock(spec=CRMServiceClient)


def test_close_account_with_crm_ticket_pipeline(
    mocker,
    mpt_client,
    config,
    order_close_account,
    aws_client_factory,
    service_client,
    fulfillment_parameters_factory,
    data_aws_account_factory,
    service_request_ticket_factory,
):

    aws_client, mock_client = aws_client_factory(
        config, "test_account_id", "test_role_name"
    )
    mock_client.close_account.return_value = {}
    mock_client.list_accounts.return_value = {
        "Accounts": [data_aws_account_factory(status="ACTIVE")]
    }
    service_client.create_service_request.return_value = {"id": "1234-5678"}
    service_client.get_service_requests.return_value = service_request_ticket_factory(
        ticket_id="1234-5678", state="New"
    )
    context = CloseAccountContext.from_order(order_close_account)
    mocker.patch(
        "swo_aws_extension.flows.steps.service_crm_steps.get_service_client",
        return_value=service_client,
    )
    mocker.patch(
        "swo_aws_extension.flows.steps.service_crm_steps.update_order",
    )

    mock_get_template = mocker.patch(
        "swo_aws_extension.flows.steps.complete_order.get_product_template_or_default",
        return_value="template",
    )
    mock_complete_order = mocker.patch(
        "swo_aws_extension.flows.steps.complete_order.complete_order",
        return_value=order_close_account,
    )

    # Creates tickets and awaits completion
    close_account_pipeline.run(mpt_client, context)

    updated_order = set_crm_ticket_id(context.order, "1234-5678")
    context.order = updated_order

    # Ticket exist but it is in progress
    close_account_pipeline.run(mpt_client, context)
    service_client.create_service_request.assert_called_once()

    # Ticket is completed
    service_client.get_service_requests.return_value = service_request_ticket_factory(
        ticket_id="1234-5678", state=CRM_TICKET_COMPLETED_STATE
    )
    mock_get_template.assert_not_called()
    # Next run of the pipeline should finish the order
    close_account_pipeline.run(mpt_client, context)
    mock_complete_order.assert_called_once()


def test_close_account_without_crm_ticket_pipeline(
    mocker,
    mpt_client,
    config,
    order_close_account,
    aws_client_factory,
    service_client,
    fulfillment_parameters_factory,
    data_aws_account_factory,
):

    aws_client, mock_client = aws_client_factory(
        config, "test_account_id", "test_role_name"
    )
    mock_client.close_account.return_value = {}
    mock_client.list_accounts.return_value = {
        "Accounts": [
            data_aws_account_factory(status="ACTIVE"),
            data_aws_account_factory(status="ACTIVE"),
        ]
    }
    context = CloseAccountContext.from_order(order_close_account)
    mocker.patch(
        "swo_aws_extension.flows.steps.service_crm_steps.get_service_client",
        return_value=service_client,
    )
    mocker.patch(
        "swo_aws_extension.flows.steps.service_crm_steps.get_service_client",
        return_value=service_client,
    )
    mocker.patch(
        "swo_aws_extension.flows.steps.service_crm_steps.update_order",
    )

    mocker.patch(
        "swo_aws_extension.flows.steps.complete_order.get_product_template_or_default",
        return_value="template",
    )
    mock_complete_order = mocker.patch(
        "swo_aws_extension.flows.steps.complete_order.complete_order",
        return_value=order_close_account,
    )

    # Runs and no ticket is created
    close_account_pipeline.run(mpt_client, context)
    service_client.create_service_request.assert_not_called()
    mock_complete_order.assert_called_once()


def test_close_account_with_multiple_termination(
    mocker,
    mpt_client,
    config,
    order_termination_close_account_multiple,
    aws_client_factory,
    service_client,
    fulfillment_parameters_factory,
    data_aws_account_factory,
):

    accounts_to_close = ["000000001", "000000002", "000000003"]
    aws_client, mock_client = aws_client_factory(
        config, "test_account_id", "test_role_name"
    )
    mock_client.close_account.return_value = {}
    list_accounts = [
        data_aws_account_factory(status="ACTIVE", id="000000001"),
        data_aws_account_factory(status="ACTIVE", id="000000002"),
        data_aws_account_factory(status="ACTIVE", id="000000003"),
        data_aws_account_factory(status="ACTIVE", id="000000004"),
        data_aws_account_factory(status="ACTIVE", id="000000005"),
        data_aws_account_factory(status="ACTIVE", id="MPA_ACCOUNT_ID"),
        data_aws_account_factory(status="ACTIVE", id="other_account"),
    ]
    mock_client.list_accounts.return_value = {"Accounts": list_accounts}
    context = CloseAccountContext.from_order(order_termination_close_account_multiple)
    mocker.patch(
        "swo_aws_extension.flows.steps.service_crm_steps.get_service_client",
        return_value=service_client,
    )
    mocker.patch(
        "swo_aws_extension.flows.steps.service_crm_steps.get_service_client",
        return_value=service_client,
    )
    mocker.patch(
        "swo_aws_extension.flows.steps.service_crm_steps.update_order",
    )

    mocker.patch(
        "swo_aws_extension.flows.steps.complete_order.get_product_template_or_default",
        return_value="template",
    )
    mock_complete_order = mocker.patch(
        "swo_aws_extension.flows.steps.complete_order.complete_order",
        return_value=context.order,
    )

    # Runs and no ticket is created
    for _ in range(len(accounts_to_close)):
        close_account_pipeline.run(mpt_client, context)
        list_accounts.pop(0)
        mock_client.list_accounts.return_value = {"Accounts": list_accounts}

    service_client.create_service_request.assert_not_called()

    expected_close_account_calls = [
        call(AccountId="000000001"),
        call(AccountId="000000002"),
        call(AccountId="000000003"),
    ]

    mock_client.close_account.assert_has_calls(expected_close_account_calls)

    mock_complete_order.assert_called_once()
