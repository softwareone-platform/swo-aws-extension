import pytest
from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.constants import CRM_TICKET_RESOLVED_STATE, TransferTypesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.service_crm_steps import (
    AwaitTransferRequestTicketWithOrganizationStep,
    CreateTransferRequestTicketWithOrganizationStep,
)
from swo_aws_extension.parameters import get_link_account_service_ticket_id


@pytest.fixture()
def order_transfer_with_organization(
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
):
    return order_factory(
        order_parameters=order_parameters_factory(
            transfer_type=TransferTypesEnum.TRANSFER_WITH_ORGANIZATION,
            master_payer_id="123456789",
        ),
        fulfillment_parameters=fulfillment_parameters_factory(
            existing_account_crm_ticket="",
        ),
    )


@pytest.fixture()
def order_transfer_with_organization_without_master_payer_id(
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
):
    return order_factory(
        order_parameters=order_parameters_factory(
            transfer_type=TransferTypesEnum.TRANSFER_WITH_ORGANIZATION,
            master_payer_id="",
        ),
        fulfillment_parameters=fulfillment_parameters_factory(
            existing_account_crm_ticket="",
        ),
    )


@pytest.fixture()
def order_transfer_with_organization_and_ticket(
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
):
    return order_factory(
        order_parameters=order_parameters_factory(
            transfer_type=TransferTypesEnum.TRANSFER_WITH_ORGANIZATION,
        ),
        fulfillment_parameters=fulfillment_parameters_factory(
            existing_account_crm_ticket="CS0004728",
        ),
    )


def test_create_transfer_request_ticket_with_organization_step_creates_ticket(
    mocker,
    order_transfer_with_organization,
    service_client,
):
    context = PurchaseContext(order=order_transfer_with_organization)
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    next_step_mock = mocker.Mock()

    service_client.create_service_request.return_value = {"id": "CS0004721"}
    update_order_mock = mocker.patch(
        "swo_aws_extension.flows.steps.service_crm_steps.update_order",
    )

    step = CreateTransferRequestTicketWithOrganizationStep()
    step(mpt_client_mock, context, next_step_mock)

    service_client.create_service_request.assert_called_once()
    update_order_mock.assert_called_once()
    assert get_link_account_service_ticket_id(context.order) == "CS0004721"
    next_step_mock.assert_called_once()


def test_create_transfer_request_ticket_raise_exception(
    mocker,
    order_transfer_with_organization_without_master_payer_id,
    service_client,
):
    context = PurchaseContext(order=order_transfer_with_organization_without_master_payer_id)
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    next_step_mock = mocker.Mock()

    service_client.create_service_request.return_value = {"id": "CS0004721"}
    update_order_mock = mocker.patch(
        "swo_aws_extension.flows.steps.service_crm_steps.update_order",
    )

    step = CreateTransferRequestTicketWithOrganizationStep()
    with pytest.raises(ValueError):
        step(mpt_client_mock, context, next_step_mock)

    service_client.create_service_request.assert_not_called()
    update_order_mock.assert_not_called()

    next_step_mock.assert_not_called()


def test_create_transfer_request_ticket_with_organization_step_ticket_exist(
    mocker,
    order_transfer_with_organization_and_ticket,
    service_client,
):
    """
    Test that the step does not create a ticket if it already exists for a transfer
    with organization.
    """
    context = PurchaseContext(order=order_transfer_with_organization_and_ticket)
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    next_step_mock = mocker.Mock()
    assert get_link_account_service_ticket_id(context.order) == "CS0004728"
    update_order_mock = mocker.patch("swo_aws_extension.flows.steps.service_crm_steps.update_order")

    step = CreateTransferRequestTicketWithOrganizationStep()
    step(mpt_client_mock, context, next_step_mock)

    service_client.create_service_request.assert_not_called()
    update_order_mock.assert_not_called()
    next_step_mock.assert_called_once()


def test_create_transfer_request_ticket_skipped(mocker, order, service_client):
    """
    Test that the step is skipped for orders that are not transfer with organization.
    """
    context = PurchaseContext(order=order)
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    next_step_mock = mocker.Mock()

    update_order_mock = mocker.patch("swo_aws_extension.flows.steps.service_crm_steps.update_order")

    step = CreateTransferRequestTicketWithOrganizationStep()
    step(mpt_client_mock, context, next_step_mock)

    service_client.create_service_request.assert_not_called()
    update_order_mock.assert_not_called()
    next_step_mock.assert_called_once()


def test_await_ticket(mocker, order_transfer_with_organization_and_ticket, service_client):
    """
    Test await ticket if it is not in completed state
    """
    context = PurchaseContext(order=order_transfer_with_organization_and_ticket)
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    next_step_mock = mocker.Mock()

    service_client.get_service_requests.return_value = {
        "id": "CS0004728",
        "state": "New",
    }
    step = AwaitTransferRequestTicketWithOrganizationStep()
    step(mpt_client_mock, context, next_step_mock)
    next_step_mock.assert_not_called()


def test_await_ticket_continue_if_completed(
    mocker, order_transfer_with_organization_and_ticket, service_client
):
    """
    Test awaiting ticket if ticket is completed
    """
    context = PurchaseContext(order=order_transfer_with_organization_and_ticket)
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    next_step_mock = mocker.Mock()

    service_client.get_service_requests.return_value = {
        "id": "CS0004728",
        "state": CRM_TICKET_RESOLVED_STATE,
    }
    step = AwaitTransferRequestTicketWithOrganizationStep()
    step(mpt_client_mock, context, next_step_mock)
    next_step_mock.assert_called_once()


def test_skip_await_ticket(mocker, order):
    """
    Test skipping ticket if not set
    """
    context = PurchaseContext(order=order)
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    next_step_mock = mocker.Mock()

    step = AwaitTransferRequestTicketWithOrganizationStep()
    step(mpt_client_mock, context, next_step_mock)
    next_step_mock.assert_called_once()
