import pytest

from swo_aws_extension.constants import (
    PARAM_ACCOUNT_EMAIL,
    OrderParameter,
    TerminationParameterChoices,
)
from swo_aws_extension.flows.close_account.flow import (
    close_account_pipeline as _close_account_pipeline,
)
from swo_aws_extension.flows.order import ORDER_TYPE_TERMINATION, CloseAccountContext


@pytest.fixture()
def close_account_pipeline_factory(mocker):
    def factory():
        mocker.patch(
            'swo_aws_extension.flows.close_account.flow.get_service_client'
        )
    return factory


@pytest.fixture()
def order_close_account_paramaters():
        def _order_parameters(
                account_email="test@aws.com",
                termination_type=TerminationParameterChoices.CLOSE_ACCOUNT,
                accont_id="1234-5678"
        ):
            return [
                {
                    "id": "PAR-1234-5678",
                    "name": "AWS account email",
                    "externalId": PARAM_ACCOUNT_EMAIL,
                    "type": "SingleLineText",
                    "value": account_email,
                },
                {
                    "id": "PAR-1234-5678",
                    "name": "Account Termination Type",
                    "externalId": OrderParameter.TERMINATION,
                    "type": "Choice",
                    "value": termination_type,
                },
                {
                    "id": "PAR-1234-5678",
                    "name": "Account Id",
                    "externalId": OrderParameter.ACCOUNT_ID,
                    "type": "SingleLineText",
                    "value": accont_id,
                }
            ]

        return _order_parameters


@pytest.fixture()
def order_close_account(order_factory, order_parameters_factory):
    order = order_factory(
        order_type=ORDER_TYPE_TERMINATION,
        order_parameters=order_parameters_factory(
            account_email="test@aws.com",
            account_id="1234-5678",
            termination_type=TerminationParameterChoices.CLOSE_ACCOUNT,
        ),
    )
    return order


@pytest.fixture()
def close_account_pipeline(settings):
    return _close_account_pipeline


@pytest.fixture()
def service_client(mocker):
    from swo_crm_service_client.client import CRMServiceClient
    return mocker.Mock(spec=CRMServiceClient)


def test_close_account_pipeline(
    mocker,
    mpt_client,
    config,
    order_close_account,
    close_account_pipeline,
    aws_client_factory,
    service_client
):

    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.close_account.return_value = {}
    mock_client.list_accounts.return_value = {"Accounts": [{'Status': 'ACTIVE'}]}
    service_client.create_service_request.return_value = {"id": "1234-5678"}
    service_client.get_service_requests.return_value = {"id": "1234-5678", "status": "created"}
    context = CloseAccountContext.from_order(order_close_account)
    mocker.patch(
        "swo_aws_extension.flows.steps.create_service_crm_ticket.get_service_client",
        return_value=service_client
    )
    mocker.patch(
        "swo_aws_extension.flows.steps.await_crm_ticket.get_service_client",
        return_value=service_client
    )
    mocker.patch(
        "swo_aws_extension.flows.close_account.last_account_ticket.update_order",
    )
    close_account_pipeline.run(mpt_client, context)


