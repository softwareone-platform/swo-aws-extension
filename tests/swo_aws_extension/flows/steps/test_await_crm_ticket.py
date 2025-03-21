from unittest.mock import Mock, create_autospec

import pytest
from swo.mpt.client import MPTClient

from swo_aws_extension.constants import CRM_TICKET_COMPLETED_STATE
from swo_aws_extension.flows.order import CloseAccountContext
from swo_aws_extension.flows.steps.await_crm_ticket import AwaitCRMTicketStatusStep
from swo_crm_service_client.client import CRMServiceClient


@pytest.fixture()
def crm_service_client():
    return Mock(spec=CRMServiceClient)


@pytest.fixture()
def get_ticket_id():
    return Mock()


@pytest.fixture()
def await_crm_ticket_status(mocker, crm_service_client, get_ticket_id):
    mocker.patch(
        "swo_aws_extension.flows.steps.await_crm_ticket.get_service_client",
        return_value=crm_service_client
    )
    return AwaitCRMTicketStatusStep(get_ticket_id, target_status=CRM_TICKET_COMPLETED_STATE)


@pytest.fixture()
def context():
    return create_autospec(CloseAccountContext, instance=True)


@pytest.fixture()
def next_step():
    return Mock()


def test_await_crm_ticket_status_initialization():
    get_ticket_id = Mock()
    skip_if_no_ticket = True

    await_crm_ticket_status = AwaitCRMTicketStatusStep(
        get_ticket_id,
        CRM_TICKET_COMPLETED_STATE,
        skip_if_no_ticket=True
    )

    assert await_crm_ticket_status.get_ticket_id == get_ticket_id
    assert await_crm_ticket_status.target_status == [CRM_TICKET_COMPLETED_STATE]
    assert await_crm_ticket_status.skip_if_no_ticket == skip_if_no_ticket

    await_crm_ticket_status = AwaitCRMTicketStatusStep(
        get_ticket_id,
        [CRM_TICKET_COMPLETED_STATE, "Closed"],
        skip_if_no_ticket=False
    )

    assert await_crm_ticket_status.get_ticket_id == get_ticket_id
    assert await_crm_ticket_status.target_status == [CRM_TICKET_COMPLETED_STATE, "Closed"]
    assert await_crm_ticket_status.skip_if_no_ticket is False


def test_await_crm_ticket_status_no_ticket_id_skip(
        await_crm_ticket_status,
        crm_service_client,
        get_ticket_id,
        context,
        next_step
    ):
    client = Mock(spec=MPTClient)
    get_ticket_id.return_value = None

    await_crm_ticket_status(client, context, next_step)

    get_ticket_id.assert_called_once_with(context)
    crm_service_client.get_service_requests.assert_not_called()
    next_step.assert_called_once_with(client, context)


def test_await_crm_ticket_status_no_ticket_id_raise(
        await_crm_ticket_status,
        crm_service_client,
        get_ticket_id,
        context,
        next_step
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
        service_request_ticket_factory
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
        service_request_ticket_factory
    ):
    client = Mock(spec=MPTClient)
    get_ticket_id.return_value = "CS001"
    crm_service_client.get_service_requests.return_value = service_request_ticket_factory(
        ticket_id="CS001",
        state=CRM_TICKET_COMPLETED_STATE
    )

    await_crm_ticket_status(client, context, next_step)

    get_ticket_id.assert_called_once_with(context)
    crm_service_client.get_service_requests.assert_called_once_with(context.order_id, "CS001")
    next_step.assert_called_once_with(client, context)
