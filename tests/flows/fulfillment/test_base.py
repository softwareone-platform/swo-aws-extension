import pytest
from mpt_extension_sdk.flows.context import (
    ORDER_TYPE_CHANGE,
    ORDER_TYPE_PURCHASE,
    ORDER_TYPE_TERMINATION,
)

from swo_aws_extension.aws.errors import AWSHttpError
from swo_aws_extension.constants import (
    CRM_TERMINATION_ADDITIONAL_INFO,
    CRM_TERMINATION_SUMMARY,
    CRM_TERMINATION_TITLE,
    CRM_TICKET_RESOLVED_STATE,
    AccountTypesEnum,
    TransferTypesEnum,
)
from swo_aws_extension.flows.error import strip_trace_id
from swo_aws_extension.flows.fulfillment import fulfill_order
from swo_aws_extension.flows.fulfillment.base import setup_contexts
from swo_aws_extension.flows.order import InitialAWSContext, TerminateContext
from swo_aws_extension.parameters import set_crm_termination_ticket_id
from swo_crm_service_client import ServiceRequest


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
    context = InitialAWSContext.from_order_data(new_order)
    with pytest.raises(AWSHttpError):
        fulfill_order(mocker.MagicMock(), context)

    process, order_id, tb = mocked_notify.mock_calls[0].args
    assert process == "fulfillment"
    assert order_id == new_order["id"]
    assert strip_trace_id(str(error)) in tb


def test_setup_contexts(mpt_client, order_factory, agreement_factory):
    orders = [order_factory(agreement=agreement_factory(vendor_id="123456789012"))]
    contexts = setup_contexts(mpt_client, orders)
    assert len(contexts) == 1
    assert contexts[0].order == orders[0]


def test_setup_contexts_without_mpa_account_id(
    mocker,
    mpt_client,
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
    mpa_pool_factory,
    buyer,
):
    order_without_mpa = order_factory(
        order_id="ORD-1",
        fulfillment_parameters=fulfillment_parameters_factory(),
    )
    order_without_mpa_2 = order_factory(
        order_id="ORD-2",
        fulfillment_parameters=fulfillment_parameters_factory(),
    )

    orders = [order_without_mpa, order_without_mpa_2]
    mocked_master_payer_account_pool_model = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.airtable.models.get_master_payer_account_pool_model",
        return_value=mocked_master_payer_account_pool_model,
    )
    mpa_pool = mpa_pool_factory()
    mocked_master_payer_account_pool_model.all.return_value = [
        mpa_pool,
        mpa_pool,
        mpa_pool,
    ]

    contexts = setup_contexts(mpt_client, orders)
    assert len(contexts) == 2
    context_without_mpa = InitialAWSContext.from_order_data(
        order_factory(
            order_id="ORD-1",
            fulfillment_parameters=fulfillment_parameters_factory(),
        )
    )
    context_without_mpa.airtable_mpa = mpa_pool
    context_without_mpa_2 = InitialAWSContext.from_order_data(
        order_factory(
            order_id="ORD-2",
            fulfillment_parameters=fulfillment_parameters_factory(),
        )
    )
    context_without_mpa_2.airtable_mpa = mpa_pool
    assert contexts[0] == context_without_mpa
    assert contexts[0].airtable_mpa == mpa_pool
    assert contexts[1] == context_without_mpa_2
    assert contexts[1].airtable_mpa == mpa_pool

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
        fulfillment_parameters=fulfillment_parameters_factory(),
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
    service_client,
):
    _, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.close_account.return_value = {}
    mock_client.list_accounts.return_value = {
        "Accounts": [data_aws_account_factory(status="ACTIVE")]
    }
    service_client.create_service_request.return_value = {"id": "1234-5678"}
    service_client.get_service_requests.return_value = service_request_ticket_factory(
        ticket_id="1234-5678", state="New"
    )
    context = TerminateContext.from_order_data(order_close_account)
    mocker.patch(
        "swo_aws_extension.flows.steps.service_crm_steps.get_service_client",
        return_value=service_client,
    )
    mocker.patch(
        "swo_aws_extension.flows.steps.service_crm_steps.update_order",
    )

    mocker.patch(
        "swo_aws_extension.flows.order.get_product_template_or_default",
        return_value="template",
    )
    complete_order_mock = mocker.patch(
        "swo_aws_extension.flows.steps.complete_order.complete_order",
        return_value=order_close_account,
    )
    template = {"id": "TPL-964-112", "name": "template-name"}
    mocker.patch(
        "swo_aws_extension.flows.order.get_product_template_or_default",
        return_value=template,
    )

    # Creates tickets and awaits completion
    fulfill_order(mpt_client, context)

    updated_order = set_crm_termination_ticket_id(context.order, "1234-5678")
    context.order = updated_order

    # Ticket exist but it is in progress
    fulfill_order(mpt_client, context)
    accounts = ", ".join(context.terminating_subscriptions_aws_account_ids)
    summary = CRM_TERMINATION_SUMMARY.format(
        accounts=accounts,
        termination_type=context.termination_type,
        mpa_account=context.mpa_account,
        order_id=context.order_id,
    )
    expected_created_service_call = (
        "ORD-0792-5000-2253-4210",
        ServiceRequest(
            additional_info=CRM_TERMINATION_ADDITIONAL_INFO,
            title=CRM_TERMINATION_TITLE.format(mpa_account=context.mpa_account),
            summary=summary,
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


@pytest.fixture()
def pipeline_mock_purchase_transfer_with_organization(mocker):
    mock = mocker.patch(
        "swo_aws_extension.flows.fulfillment.base.purchase_transfer_with_organization.run",
    )
    return mock


@pytest.fixture()
def pipeline_mock_purchase_transfer_without_organization(mocker):
    mock = mocker.patch(
        "swo_aws_extension.flows.fulfillment.base.purchase_transfer_without_organization.run",
    )
    return mock


@pytest.fixture()
def pipeline_mock_purchase_split_billing(mocker):
    mock = mocker.patch(
        "swo_aws_extension.flows.fulfillment.base.purchase_split_billing.run",
    )
    return mock


@pytest.fixture()
def pipeline_mock_change_order(mocker):
    mock = mocker.patch(
        "swo_aws_extension.flows.fulfillment.base.change_order.run",
    )
    return mock


@pytest.fixture()
def pipeline_mock_purchase(mocker):
    mock = mocker.patch(
        "swo_aws_extension.flows.fulfillment.base.purchase.run",
    )
    return mock


@pytest.fixture()
def pipeline_mock_terminate(mocker):
    mock = mocker.patch(
        "swo_aws_extension.flows.fulfillment.base.terminate.run",
    )
    return mock


def test_is_type_transfer_with_organization(
    mocker,
    order_factory,
    order_parameters_factory,
    pipeline_mock_purchase_transfer_with_organization,
    pipeline_mock_purchase_transfer_without_organization,
    pipeline_mock_purchase,
    pipeline_mock_change_order,
    pipeline_mock_terminate,
):
    order = order_factory(
        order_type=ORDER_TYPE_PURCHASE,
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_ACCOUNT,
            transfer_type=TransferTypesEnum.TRANSFER_WITH_ORGANIZATION,
        ),
    )
    fulfill_order(mocker.MagicMock(), InitialAWSContext.from_order_data(order))

    pipeline_mock_purchase_transfer_with_organization.assert_called_once()
    pipeline_mock_purchase_transfer_without_organization.assert_not_called()
    pipeline_mock_purchase.assert_not_called()
    pipeline_mock_change_order.assert_not_called()
    pipeline_mock_terminate.assert_not_called()


def test_is_type_transfer_without_organization(
    mocker,
    order_factory,
    order_parameters_factory,
    pipeline_mock_purchase_transfer_with_organization,
    pipeline_mock_purchase_transfer_without_organization,
    pipeline_mock_purchase,
    pipeline_mock_change_order,
    pipeline_mock_terminate,
):
    order = order_factory(
        order_type=ORDER_TYPE_PURCHASE,
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_ACCOUNT,
            transfer_type=TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION,
        ),
    )
    fulfill_order(mocker.MagicMock(), InitialAWSContext.from_order_data(order))

    pipeline_mock_purchase_transfer_with_organization.assert_not_called()
    pipeline_mock_purchase_transfer_without_organization.assert_called_once()
    pipeline_mock_purchase.assert_not_called()
    pipeline_mock_change_order.assert_not_called()
    pipeline_mock_terminate.assert_not_called()


def test_is_type_split_billing(
    mocker,
    order_factory,
    order_parameters_factory,
    pipeline_mock_purchase_transfer_with_organization,
    pipeline_mock_purchase_transfer_without_organization,
    pipeline_mock_purchase_split_billing,
    pipeline_mock_purchase,
    pipeline_mock_change_order,
    pipeline_mock_terminate,
):
    order = order_factory(
        order_type=ORDER_TYPE_PURCHASE,
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_ACCOUNT,
            transfer_type=TransferTypesEnum.SPLIT_BILLING,
        ),
    )
    fulfill_order(mocker.MagicMock(), InitialAWSContext(order=order))

    pipeline_mock_purchase_transfer_with_organization.assert_not_called()
    pipeline_mock_purchase_transfer_without_organization.assert_not_called()
    pipeline_mock_purchase_split_billing.assert_called_once()
    pipeline_mock_purchase.assert_not_called()
    pipeline_mock_change_order.assert_not_called()
    pipeline_mock_terminate.assert_not_called()


def test_is_type_purchase(
    mocker,
    order_factory,
    order_parameters_factory,
    pipeline_mock_purchase_transfer_with_organization,
    pipeline_mock_purchase_transfer_without_organization,
    pipeline_mock_purchase,
    pipeline_mock_change_order,
    pipeline_mock_terminate,
):
    order = order_factory(
        order_type=ORDER_TYPE_PURCHASE,
        order_parameters=order_parameters_factory(
            account_type="",
            transfer_type="",
        ),
    )
    fulfill_order(mocker.MagicMock(), InitialAWSContext.from_order_data(order))

    pipeline_mock_purchase_transfer_with_organization.assert_not_called()
    pipeline_mock_purchase_transfer_without_organization.assert_not_called()
    pipeline_mock_purchase.assert_called_once()
    pipeline_mock_change_order.assert_not_called()
    pipeline_mock_terminate.assert_not_called()


def test_is_type_change_order(
    mocker,
    order_factory,
    order_parameters_factory,
    pipeline_mock_purchase_transfer_with_organization,
    pipeline_mock_purchase_transfer_without_organization,
    pipeline_mock_purchase,
    pipeline_mock_change_order,
    pipeline_mock_terminate,
):
    order = order_factory(
        order_type=ORDER_TYPE_CHANGE,
        order_parameters=order_parameters_factory(
            account_type="",
            transfer_type="",
        ),
    )
    fulfill_order(mocker.MagicMock(), InitialAWSContext.from_order_data(order))

    pipeline_mock_purchase_transfer_with_organization.assert_not_called()
    pipeline_mock_purchase_transfer_without_organization.assert_not_called()
    pipeline_mock_purchase.assert_not_called()
    pipeline_mock_change_order.assert_called_once()
    pipeline_mock_terminate.assert_not_called()


def test_is_type_termination(
    mocker,
    order_factory,
    order_parameters_factory,
    pipeline_mock_purchase_transfer_with_organization,
    pipeline_mock_purchase_transfer_without_organization,
    pipeline_mock_purchase,
    pipeline_mock_change_order,
    pipeline_mock_terminate,
):
    order = order_factory(
        order_type=ORDER_TYPE_TERMINATION,
        order_parameters=order_parameters_factory(
            account_type="",
            transfer_type="",
        ),
    )
    fulfill_order(mocker.MagicMock(), InitialAWSContext.from_order_data(order))

    pipeline_mock_purchase_transfer_with_organization.assert_not_called()
    pipeline_mock_purchase_transfer_without_organization.assert_not_called()
    pipeline_mock_purchase.assert_not_called()
    pipeline_mock_change_order.assert_not_called()
    pipeline_mock_terminate.assert_called_once()


def test_is_type_unknown(
    mocker,
    order_factory,
    order_parameters_factory,
    pipeline_mock_purchase_transfer_with_organization,
    pipeline_mock_purchase_transfer_without_organization,
    pipeline_mock_purchase,
    pipeline_mock_change_order,
    pipeline_mock_terminate,
):
    order = order_factory(
        order_type="unknown",
        order_parameters=order_parameters_factory(
            account_type="",
            transfer_type="",
        ),
    )
    teams_notification = mocker.patch(
        "swo_aws_extension.flows.fulfillment.base.notify_unhandled_exception_in_teams"
    )
    with pytest.raises(RuntimeError):
        fulfill_order(mocker.MagicMock(), InitialAWSContext.from_order_data(order))

    pipeline_mock_purchase_transfer_with_organization.assert_not_called()
    pipeline_mock_purchase_transfer_without_organization.assert_not_called()
    pipeline_mock_purchase.assert_not_called()
    pipeline_mock_change_order.assert_not_called()
    pipeline_mock_terminate.assert_not_called()
    teams_notification.assert_called_once()
