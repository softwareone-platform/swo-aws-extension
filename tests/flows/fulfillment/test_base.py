import pytest

from swo_aws_extension.aws.errors import AWSHttpError
from swo_aws_extension.constants import CRM_TICKET_RESOLVED_STATE
from swo_aws_extension.flows.error import strip_trace_id
from swo_aws_extension.flows.fulfillment import fulfill_order
from swo_aws_extension.flows.fulfillment.base import setup_contexts
from swo_aws_extension.flows.order import InitialAWSContext, TerminateContext
from swo_aws_extension.parameters import set_crm_ticket_id
from swo_crm_service_client import CRMServiceClient, ServiceRequest


def test_fulfill_order_exception(mocker, mpt_error_factory, order_factory):
    error_data = mpt_error_factory(500, "Internal Server Error", "Oops!")
    error = AWSHttpError(500, error_data)
    mocked_notify = mocker.patch(
        "swo_aws_extension.flows.fulfillment.base.notify_unhandled_exception_in_teams"
    )
    mocker.patch(
        "swo_aws_extension.flows.fulfillment.base.purchase.run",
        side_effect=error,
    )

    new_order = order_factory(order_id="ORD-FFFF")
    context = InitialAWSContext(order=new_order)
    with pytest.raises(AWSHttpError):
        fulfill_order(mocker.MagicMock(), context)

    process, order_id, tb = mocked_notify.mock_calls[0].args
    assert process == "fulfillment"
    assert order_id == new_order["id"]
    assert strip_trace_id(str(error)) in tb


def test_setup_contexts(mpt_client, order_factory):
    orders = [order_factory()]
    contexts = setup_contexts(mpt_client, orders)
    assert len(contexts) == 1
    assert contexts[0].order == orders[0]


def test_setup_contexts_without_mpa_account_id(
    mocker,
    mpt_client,
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
    mpa_pool,
    buyer,
):
    order_without_mpa = order_factory(
        order_id="ORD-1",
        fulfillment_parameters=fulfillment_parameters_factory(mpa_account_id=""),
    )

    orders = [order_without_mpa]
    mocked_master_payer_account_pool_model = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.airtable.models.get_master_payer_account_pool_model",
        return_value=mocked_master_payer_account_pool_model,
    )
    mocked_master_payer_account_pool_model.all.return_value = [mpa_pool]

    contexts = setup_contexts(mpt_client, orders)
    assert len(contexts) == 1
    assert contexts[0] == InitialAWSContext(order=order_without_mpa, airtable_mpa=mpa_pool)
    assert contexts[0].airtable_mpa == mpa_pool

    mocked_master_payer_account_pool_model.all.assert_called_once()


def test_setup_contexts_without_mpa_account_id_empty_pool(
    mocker,
    mpt_client,
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
    buyer,
):
    order_without_mpa = order_factory(
        order_id="ORD-1",
        fulfillment_parameters=fulfillment_parameters_factory(mpa_account_id=""),
    )

    orders = [order_without_mpa]
    mocked_master_payer_account_pool_model = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.airtable.models.get_master_payer_account_pool_model",
        return_value=mocked_master_payer_account_pool_model,
    )
    mocked_master_payer_account_pool_model.all.return_value = []

    contexts = setup_contexts(mpt_client, orders)
    assert len(contexts) == 1
    assert contexts[0].order == order_without_mpa
    assert contexts[0].airtable_mpa is None

    mocked_master_payer_account_pool_model.all.assert_called_once()


def test_fulfill_terminate_account_flow(
    mocker,
    mpt_client,
    config,
    order_close_account,
    aws_client_factory,
    fulfillment_parameters_factory,
    data_aws_account_factory,
    service_request_ticket_factory,
):
    service_client = mocker.Mock(spec=CRMServiceClient)
    _, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.close_account.return_value = {}
    mock_client.list_accounts.return_value = {
        "Accounts": [data_aws_account_factory(status="ACTIVE")]
    }
    service_client.create_service_request.return_value = {"id": "1234-5678"}
    service_client.get_service_requests.return_value = service_request_ticket_factory(
        ticket_id="1234-5678", state="New"
    )
    context = TerminateContext(order=order_close_account)
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
    complete_order_mock = mocker.patch(
        "swo_aws_extension.flows.steps.complete_order.complete_order",
        return_value=order_close_account,
    )

    # Creates tickets and awaits completion
    fulfill_order(mpt_client, context)

    updated_order = set_crm_ticket_id(context.order, "1234-5678")
    context.order = updated_order

    # Ticket exist but it is in progress
    fulfill_order(mpt_client, context)

    expected_created_service_call = (
        "ORD-0792-5000-2253-4210",
        ServiceRequest(
            external_user_email=None,
            external_username=None,
            requester="Supplier.Portal",
            sub_service="Service Activation",
            global_academic_ext_user_id="globalacademicExtUserId",
            additional_info="additionalInfo",
            summary="\n"
            "Request of termination of AWS accounts.\n"
            "\n"
            "MPA: 123456789012\n"
            "Termination type: CloseAccount\n"
            "\n"
            "AWS Account to terminate: 1234-5678\n",
            title="Termination of account(s) linked to MPA 123456789012",
            service_type="MarketPlaceServiceActivation",
        ),
    )
    service_client.create_service_request.assert_called_once_with(*expected_created_service_call)

    # Ticket is completed
    service_client.get_service_requests.return_value = service_request_ticket_factory(
        ticket_id="1234-5678", state=CRM_TICKET_RESOLVED_STATE
    )
    complete_order_mock.assert_not_called()
    # Next run of the pipeline should finish the order
    fulfill_order(mpt_client, context)
    complete_order_mock.assert_called_once()
