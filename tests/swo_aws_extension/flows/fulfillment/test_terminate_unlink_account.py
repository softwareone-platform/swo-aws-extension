import pytest
from botocore.exceptions import ClientError

from swo_aws_extension.constants import (
    CRM_TICKET_COMPLETED_STATE,
)
from swo_aws_extension.flows.fulfillment import fulfill_order
from swo_aws_extension.flows.fulfillment.pipelines import (
    terminate as terminate_pipeline,
)
from swo_aws_extension.flows.order import TerminateContext
from swo_aws_extension.parameters import (
    OrderParametersEnum,
    set_crm_ticket_id,
)
from swo_crm_service_client.client import CRMServiceClient


@pytest.fixture()
def service_client(mocker):
    return mocker.Mock(spec=CRMServiceClient)


def test_full_successful_termination_flow_for_unlink_account_with_crm_ticket_pipeline(
    mocker,
    mpt_client,
    config,
    order_unlink_account,
    aws_client_factory,
    service_client,
    fulfillment_parameters_factory,
    data_aws_account_factory,
    service_request_ticket_factory,
):
    """
    Tests the full successful flow for unlinking an account with a CRM ticket.

    Accounts in organization: MPA + Terminating account

    - First run unlinks the account and creates ticket
    - Second run awaits ticket for completion
    - Third run ticket is completed and finishes the order

    """
    list_accounts_all = {
        "Accounts": [
            data_aws_account_factory(id="1234-5678", status="ACTIVE"),
            data_aws_account_factory(id="MPA-123456", status="ACTIVE"),
        ]
    }

    list_accounts_only_mpa = {
        "Accounts": [
            data_aws_account_factory(id="MPA-123456", status="ACTIVE"),
        ]
    }

    aws_client, mock_client = aws_client_factory(
        config, "test_account_id", "test_role_name"
    )
    mock_client.close_account.return_value = {}
    mock_client.list_accounts.side_effect = [
        # First run. Gets all accounts and unlinks one
        list_accounts_all,
        list_accounts_only_mpa,
        # Second run. Check if needs to unlink accounts
        list_accounts_only_mpa,
        # Second run. Checks if it needs to create the ticket
        list_accounts_only_mpa,
    ]
    service_client.create_service_request.return_value = {"id": "1234-5678"}
    service_client.get_service_requests.return_value = service_request_ticket_factory(
        ticket_id="1234-5678", state="New"
    )

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
        return_value=order_unlink_account,
    )

    # Creates tickets and awaits completion
    fulfill_order(mpt_client, order_unlink_account)

    order_with_ticket_id = set_crm_ticket_id(order_unlink_account, "1234-5678")

    # Ticket exist but it is in progress
    fulfill_order(mpt_client, order_with_ticket_id)

    service_client.create_service_request.assert_called_once()

    # Ticket is completed
    service_client.get_service_requests.return_value = service_request_ticket_factory(
        ticket_id="1234-5678", state=CRM_TICKET_COMPLETED_STATE
    )
    mock_get_template.assert_not_called()

    # Next run of the pipeline should finish the order
    fulfill_order(mpt_client, order_with_ticket_id)

    mock_client.remove_account_from_organization.assert_called_once()
    mock_client.close_account.assert_not_called()
    mock_complete_order.assert_called_once()


@pytest.fixture()
def remove_account_from_organization_prerequisites_exception():
    from botocore.exceptions import ClientError

    error_response = {
        "Error": {
            "Code": "ConstraintViolationException",
            "Message": "The member account is missing one or more of the prerequisites required"
            " to operate as a standalone account. To add what is missing, sign-in"
            " to the member account using the AWS Organizations console,"
            " then select to leave the organization."
            " You will then be prompted to enter any missing information.",
        }
    }

    return ClientError(
        error_response=error_response,
        operation_name="RemoveAccountFromOrganization",
    )


@pytest.fixture()
def remove_account_from_organization_cool_off_exception():
    from botocore.exceptions import ClientError

    error_response = {
        "Error": {
            "Code": "ConstraintViolationException",
            "Message": "This operation requires a wait period.  Try again later.",
        }
    }

    return ClientError(
        error_response=error_response,
        operation_name="RemoveAccountFromOrganization",
    )


def test_unlink_account_with_missing_prerequisites(
    mocker,
    mpt_client,
    config,
    order_unlink_account,
    aws_client_factory,
    service_client,
    fulfillment_parameters_factory,
    data_aws_account_factory,
    service_request_ticket_factory,
    remove_account_from_organization_prerequisites_exception,
):
    """
    Tests the case scenario where the account can't be unlinked because it is missing prerequisites.
    """
    list_accounts_all = {
        "Accounts": [
            data_aws_account_factory(id="1234-5678", status="ACTIVE"),
            data_aws_account_factory(id="MPA-123456", status="ACTIVE"),
        ]
    }

    aws_client, mock_client = aws_client_factory(
        config, "test_account_id", "test_role_name"
    )
    mock_client.remove_account_from_organization.side_effect = [
        remove_account_from_organization_prerequisites_exception
    ]
    mock_client.list_accounts.return_value = list_accounts_all
    context = TerminateContext.from_order(order_unlink_account)
    mocker.patch(
        "swo_aws_extension.flows.steps.terminate_aws_account.get_crm_ticket_id",
        return_value="",
    )
    switch_order_to_query_mock = mocker.patch(
        "swo_aws_extension.flows.steps.terminate_aws_account.switch_order_to_query",
        return_value=order_unlink_account,
    )
    set_ordering_parameter_error_mock = mocker.patch(
        "swo_aws_extension.flows.steps.terminate_aws_account.set_ordering_parameter_error",
        return_value=order_unlink_account,
    )
    # Creates tickets and awaits completion
    terminate_pipeline.run(mpt_client, context)
    error = {
        "id": "AWS005",
        "message": "The member account `1234-5678` is missing one or more of the "
        "prerequisites required to operate as a standalone account. To "
        "add what is missing, sign-in to the member account using the AWS "
        "Organizations console, then select to leave the organization. "
        "You will then be prompted to enter any missing information.",
    }
    set_ordering_parameter_error_mock.assert_called_once_with(
        context.order, OrderParametersEnum.TERMINATION, error
    )
    switch_order_to_query_mock.assert_called_once()


def test_terminate_without_terminate_type(
    mocker,
    mpt_client,
    config,
    order_terminate_without_type,
    aws_client_factory,
    service_client,
    fulfillment_parameters_factory,
    data_aws_account_factory,
    service_request_ticket_factory,
    remove_account_from_organization_prerequisites_exception,
):
    """
    Tests the scenario where a termination type has not been selected
    """
    list_accounts_all = {
        "Accounts": [
            data_aws_account_factory(id="1234-5678", status="ACTIVE"),
            data_aws_account_factory(id="MPA-123456", status="ACTIVE"),
        ]
    }

    aws_client, mock_client = aws_client_factory(
        config, "test_account_id", "test_role_name"
    )
    mock_client.remove_account_from_organization.side_effect = [
        remove_account_from_organization_prerequisites_exception
    ]
    mock_client.list_accounts.return_value = list_accounts_all
    context = TerminateContext.from_order(order_terminate_without_type)
    mocker.patch(
        "swo_aws_extension.flows.steps.terminate_aws_account.get_crm_ticket_id",
        return_value="",
    )
    switch_order_to_query_mock = mocker.patch(
        "swo_aws_extension.flows.steps.terminate_aws_account.switch_order_to_query",
        return_value=order_terminate_without_type,
    )

    # Creates tickets and awaits completion
    terminate_pipeline.run(mpt_client, context)
    switch_order_to_query_mock.assert_called_once()


def test_remove_account_from_organization_cool_off_period(
    mocker,
    mpt_client,
    config,
    order_unlink_account,
    aws_client_factory,
    service_client,
    fulfillment_parameters_factory,
    data_aws_account_factory,
    service_request_ticket_factory,
    remove_account_from_organization_cool_off_exception,
):
    """
    Tests the case scenario where the account can't be unlinked because it is missing prerequisites.
    """
    list_accounts_all = {
        "Accounts": [
            data_aws_account_factory(id="1234-5678", status="ACTIVE"),
            data_aws_account_factory(id="MPA-123456", status="ACTIVE"),
        ]
    }

    aws_client, mock_client = aws_client_factory(
        config, "test_account_id", "test_role_name"
    )
    mock_client.remove_account_from_organization.side_effect = [
        remove_account_from_organization_cool_off_exception
    ]
    mock_client.list_accounts.return_value = list_accounts_all
    context = TerminateContext.from_order(order_unlink_account)
    mocker.patch(
        "swo_aws_extension.flows.steps.terminate_aws_account.get_crm_ticket_id",
        return_value="",
    )
    next_step_call = mocker.patch(
        "swo_aws_extension.flows.steps.service_crm_steps.CreateServiceRequestStep.__call__"
    )
    # Creates tickets and awaits completion
    terminate_pipeline.run(mpt_client, context)
    next_step_call.assert_not_called()


@pytest.fixture()
def unknown_client_error():
    from botocore.exceptions import ClientError

    error_response = {
        "Error": {
            "Code": "AnotherTypeOfError",
            "Message": "Unknown error",
        }
    }

    return ClientError(
        error_response=error_response,
        operation_name="RemoveAccountFromOrganization",
    )

def test_unknown_client_error(
    mocker,
    mpt_client,
    config,
    order_unlink_account,
    aws_client_factory,
    service_client,
    fulfillment_parameters_factory,
    data_aws_account_factory,
    service_request_ticket_factory,
    unknown_client_error,
):
    """
    Tests the case scenario where the account can't be unlinked because it reach aws quota
    """
    list_accounts_all = {
        "Accounts": [
            data_aws_account_factory(id="1234-5678", status="ACTIVE"),
            data_aws_account_factory(id="MPA-123456", status="ACTIVE"),
        ]
    }

    aws_client, mock_client = aws_client_factory(
        config, "test_account_id", "test_role_name"
    )
    mock_client.remove_account_from_organization.side_effect = unknown_client_error
    mock_client.list_accounts.return_value = list_accounts_all
    context = TerminateContext.from_order(order_unlink_account)
    mocker.patch(
        "swo_aws_extension.flows.steps.terminate_aws_account.get_crm_ticket_id",
        return_value="",
    )
    next_step_call = mocker.patch(
        "swo_aws_extension.flows.steps.service_crm_steps.CreateServiceRequestStep.__call__"
    )
    # Creates tickets and awaits completion
    with pytest.raises(ClientError):
        terminate_pipeline.run(mpt_client, context)
    next_step_call.assert_not_called()
