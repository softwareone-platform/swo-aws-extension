from unittest.mock import Mock, create_autospec

import pytest
from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.constants import CRM_TICKET_RESOLVED_STATE
from swo_aws_extension.flows.order import PurchaseContext, TerminateContext
from swo_aws_extension.flows.steps.service_crm_steps import (
    AwaitCRMTicketStatusStep,
    CreateOnboardTicketStep,
    CreateServiceRequestStep,
    CreateUpdateKeeperTicketStep,
)
from swo_crm_service_client.client import CRMServiceClient, ServiceRequest


@pytest.fixture
def crm_client():
    return Mock(spec=CRMServiceClient)


@pytest.fixture
def service_request():
    return ServiceRequest(
        external_user_email="albert.sola@softwareone.com",
        external_username="albert.sola@softwareone.com",
        requester="Supplier.Portal",
        sub_service="Service Activation",
        global_academic_ext_user_id="notapplicable",
        additional_info="additionalInfo",
        summary="This is a test",
        title="This is a test from AWS Extension",
        service_type="MarketPlaceServiceActivation",
    )


@pytest.fixture
def service_request_factory(service_request):
    return Mock(return_value=service_request)


@pytest.fixture
def crm_ticket_id_saver() -> Mock:
    return Mock(return_value=None)


@pytest.fixture
def create_service_crm_ticket_step(
    mocker, crm_client, service_request_factory, crm_ticket_id_saver
):
    mocker.patch(
        "swo_aws_extension.flows.steps.service_crm_steps.get_service_client",
        return_value=crm_client,
    )

    return CreateServiceRequestStep(
        service_request_factory,
        ticket_id_saver=crm_ticket_id_saver,
        criteria=None,
    )


@pytest.fixture
def context():
    return create_autospec(TerminateContext, instance=True)


@pytest.fixture
def next_step():
    return Mock(return_value=None)


def test_create_service_crm_ticket_meets_criteria(
    create_service_crm_ticket_step,
    crm_client,
    service_request_factory,
    context,
    next_step,
    crm_ticket_id_saver,
):
    client = Mock(spec=MPTClient)
    context.order_id = "test_order_id"

    crm_client.create_service_request.return_value = {"id": "12345"}
    service_request = Mock()
    service_request_factory.return_value = service_request

    create_service_crm_ticket_step(client, context, next_step)

    service_request_factory.assert_called_once_with(context)
    crm_client.create_service_request.assert_called_once_with("test_order_id", service_request)
    next_step.assert_called_once_with(client, context)
    crm_ticket_id_saver.assert_called_once_with(client, context, "12345")


def test_create_service_crm_ticket_does_not_meet_criteria(
    create_service_crm_ticket_step,
    crm_client,
    service_request_factory,
    context,
    next_step,
    service_request,
    crm_ticket_id_saver,
):
    context.order_id = "ORD-0000-0000"
    client = Mock(spec=MPTClient)
    create_service_crm_ticket_step.criteria = lambda x: False

    create_service_crm_ticket_step(client, context, next_step)

    service_request_factory.assert_not_called()
    crm_client.create_service_request.assert_not_called()
    next_step.assert_called_once_with(client, context)
    crm_ticket_id_saver.assert_not_called()


def test_create_service_crm_ticket_does_meet_criteria(
    create_service_crm_ticket_step,
    crm_client,
    service_request_factory,
    context,
    next_step,
    service_request,
    crm_ticket_id_saver,
):
    crm_client.create_service_request.return_value = {"id": "12345"}
    client = Mock(spec=MPTClient)
    context.order_id = "ORD-0000-0000"  # Set the order_id to a string
    create_service_crm_ticket_step.criteria = lambda x: True

    create_service_crm_ticket_step(client, context, next_step)

    service_request_factory.assert_called_once_with(context)
    crm_client.create_service_request.assert_called_once_with("ORD-0000-0000", service_request)
    next_step.assert_called_once_with(client, context)
    crm_ticket_id_saver.assert_called_once_with(client, context, "12345")


@pytest.fixture
def crm_service_client():
    return Mock(spec=CRMServiceClient)


@pytest.fixture
def get_ticket_id():
    return Mock()


@pytest.fixture
def await_crm_ticket_status(mocker, crm_service_client, get_ticket_id):
    mocker.patch(
        "swo_aws_extension.flows.steps.service_crm_steps.get_service_client",
        return_value=crm_service_client,
    )
    return AwaitCRMTicketStatusStep(get_ticket_id, target_status=CRM_TICKET_RESOLVED_STATE)


def test_await_crm_ticket_status_initialization():
    get_ticket_id = Mock()
    skip_if_no_ticket = True

    await_crm_ticket_status = AwaitCRMTicketStatusStep(
        get_ticket_id, CRM_TICKET_RESOLVED_STATE, skip_if_no_ticket=True
    )

    assert await_crm_ticket_status.get_ticket_id == get_ticket_id
    assert await_crm_ticket_status.target_status == [CRM_TICKET_RESOLVED_STATE]
    assert await_crm_ticket_status.skip_if_no_ticket == skip_if_no_ticket

    await_crm_ticket_status = AwaitCRMTicketStatusStep(
        get_ticket_id, [CRM_TICKET_RESOLVED_STATE, "Closed"], skip_if_no_ticket=False
    )

    assert await_crm_ticket_status.get_ticket_id == get_ticket_id
    assert await_crm_ticket_status.target_status == [
        CRM_TICKET_RESOLVED_STATE,
        "Closed",
    ]
    assert await_crm_ticket_status.skip_if_no_ticket is False


def test_await_crm_ticket_status_no_ticket_id_skip(
    await_crm_ticket_status, crm_service_client, get_ticket_id, context, next_step
):
    client = Mock(spec=MPTClient)
    get_ticket_id.return_value = None

    await_crm_ticket_status(client, context, next_step)

    get_ticket_id.assert_called_once_with(context)
    crm_service_client.get_service_requests.assert_not_called()
    next_step.assert_called_once_with(client, context)


def test_await_crm_ticket_status_no_ticket_id_raise(
    await_crm_ticket_status, crm_service_client, get_ticket_id, context, next_step
):
    client = Mock(spec=MPTClient)
    get_ticket_id.return_value = None
    await_crm_ticket_status.skip_if_no_ticket = False

    with pytest.raises(ValueError, match="Ticket ID is required."):
        await_crm_ticket_status(client, context, next_step)

    get_ticket_id.assert_called_once_with(context)
    crm_service_client.get_service_requests.assert_not_called()
    next_step.assert_not_called()


def test_await_crm_ticket_status_ticket_not_in_target_status(
    await_crm_ticket_status,
    crm_service_client,
    get_ticket_id,
    context,
    next_step,
    service_request_ticket_factory,
):
    client = Mock(spec=MPTClient)
    get_ticket_id.return_value = "ticket_id"
    crm_service_client.get_service_requests.return_value = service_request_ticket_factory(
        state="InProgress"
    )

    await_crm_ticket_status(client, context, next_step)

    get_ticket_id.assert_called_once_with(context)
    crm_service_client.get_service_requests.assert_called_once_with(context.order_id, "ticket_id")
    next_step.assert_not_called()


def test_await_crm_ticket_status_ticket_in_target_status(
    await_crm_ticket_status,
    crm_service_client,
    get_ticket_id,
    context,
    next_step,
    service_request_ticket_factory,
):
    client = Mock(spec=MPTClient)
    get_ticket_id.return_value = "CS001"
    crm_service_client.get_service_requests.return_value = service_request_ticket_factory(
        ticket_id="CS001", state=CRM_TICKET_RESOLVED_STATE
    )

    await_crm_ticket_status(client, context, next_step)

    get_ticket_id.assert_called_once_with(context)
    crm_service_client.get_service_requests.assert_called_once_with(context.order_id, "CS001")
    next_step.assert_called_once_with(client, context)


def test_create_keeper_ticket(
    mocker, crm_client, mock_order, next_step, service_request, mpa_pool_factory
):
    mocker.patch(
        "swo_aws_extension.flows.steps.service_crm_steps.get_service_client",
        return_value=crm_client,
    )
    crm_client.create_service_request.return_value = {"id": "12345"}
    client = Mock(spec=MPTClient)
    context = PurchaseContext.from_order_data(mock_order)
    context.airtable_mpa = mpa_pool_factory()
    step = CreateUpdateKeeperTicketStep()
    step(client, context, next_step)

    crm_client.create_service_request.assert_called_once()
    next_step.assert_called_once_with(client, context)


def test_create_keeper_ticket_fail_if_not_mpa_pool(
    mocker, crm_client, mock_order, next_step, service_request
):
    crm_client.create_service_request.return_value = {"id": "12345"}
    client = Mock(spec=MPTClient)
    context = PurchaseContext.from_order_data(mock_order)
    context.airtable_mpa = None
    step = CreateUpdateKeeperTicketStep()
    with pytest.raises(RuntimeError):
        step(client, context, next_step)


def test_create_keeper_ticket_fail_it_no_ticket_id(
    mocker, crm_client, mock_order, next_step, service_request, mpa_pool_factory
):
    mocker.patch(
        "swo_aws_extension.flows.steps.service_crm_steps.get_service_client",
        return_value=crm_client,
    )
    crm_client.create_service_request.return_value = {"id": None}
    client = Mock(spec=MPTClient)
    context = PurchaseContext.from_order_data(mock_order)
    context.airtable_mpa = mpa_pool_factory()
    step = CreateUpdateKeeperTicketStep()
    with pytest.raises(ValueError):
        step(client, context, next_step)


def test_create_onboard_ticket(
    mocker, crm_client, mock_order, next_step, service_request, mpa_pool_factory
):
    mocker.patch(
        "swo_aws_extension.flows.steps.service_crm_steps.get_service_client",
        return_value=crm_client,
    )
    crm_client.create_service_request.return_value = {"id": "12345"}
    client = Mock(spec=MPTClient)
    context = PurchaseContext.from_order_data(mock_order)
    context.airtable_mpa = mpa_pool_factory()
    step = CreateOnboardTicketStep()
    step(client, context, next_step)

    crm_client.create_service_request.assert_called_once()
    next_step.assert_called_once_with(client, context)


def test_create_onboard_ticket_fail_it_no_ticket_id(
    mocker, crm_client, mock_order, next_step, service_request, mpa_pool_factory
):
    mocker.patch(
        "swo_aws_extension.flows.steps.service_crm_steps.get_service_client",
        return_value=crm_client,
    )
    crm_client.create_service_request.return_value = {"id": None}
    client = Mock(spec=MPTClient)

    context = PurchaseContext.from_order_data(mock_order)
    context.airtable_mpa = mpa_pool_factory()
    step = CreateOnboardTicketStep()
    with pytest.raises(ValueError):
        step(client, context, next_step)


def test_create_onboard_ticket_fail_if_not_mpa_pool(
    mocker, crm_client, mock_order, next_step, service_request
):
    crm_client.create_service_request.return_value = {"id": "12345"}
    client = Mock(spec=MPTClient)
    context = PurchaseContext.from_order_data(mock_order)
    context.airtable_mpa = None
    step = CreateUpdateKeeperTicketStep()
    with pytest.raises(RuntimeError):
        step(client, context, next_step)


def test_create_onboard_require_attention_ticket(
    mocker,
    crm_client,
    next_step,
    service_request,
    mpa_pool_factory,
    order_factory,
    fulfillment_parameters_factory,
):
    mocker.patch(
        "swo_aws_extension.flows.steps.service_crm_steps.get_service_client",
        return_value=crm_client,
    )
    crm_client.create_service_request.return_value = {"id": "12345"}
    client = Mock(spec=MPTClient)
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(crm_ccp_ticket_id="12345")
    )
    context = PurchaseContext.from_order_data(order)
    context.airtable_mpa = mpa_pool_factory()
    step = CreateOnboardTicketStep()
    step(client, context, next_step)

    crm_client.create_service_request.assert_called_once()
    next_step.assert_called_once_with(client, context)
