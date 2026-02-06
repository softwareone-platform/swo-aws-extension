import pytest

from swo_aws_extension.constants import CRM_TICKET_RESOLVED_STATE
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.crm_tickets.templates.models import CRMTicketTemplate
from swo_aws_extension.flows.steps.crm_tickets.ticket_manager import TicketManager
from swo_aws_extension.flows.steps.errors import UnexpectedStopError
from swo_aws_extension.swo.crm_service.client import ServiceRequest
from swo_aws_extension.swo.crm_service.errors import CRMError


@pytest.fixture
def ticket_template():
    return CRMTicketTemplate(
        title="Test Ticket Title",
        additional_info="Additional info for the ticket",
        summary="Summary with {placeholder}",
    )


@pytest.fixture
def ticket_manager(config, ticket_template):
    return TicketManager(config=config, ticket_name="Test Ticket", template=ticket_template)


def test_create_new_ticket_returns_ticket_id(
    order_factory,
    fulfillment_parameters_factory,
    mock_crm_client,
    ticket_manager,
):
    order = order_factory(fulfillment_parameters=fulfillment_parameters_factory())
    context = PurchaseContext.from_order_data(order)
    summary = "Formatted summary"
    mock_crm_client.return_value.create_service_request.return_value = {"id": "TICKET-456"}

    result = ticket_manager.create_new_ticket(context, summary)

    assert result == "TICKET-456"
    mock_crm_client.return_value.create_service_request.assert_called_once_with(
        context.order_id,
        ServiceRequest(
            additional_info=ticket_manager.template.additional_info,
            summary=summary,
            title=ticket_manager.template.title,
        ),
    )


def test_create_new_ticket_raises_unexpected_stop_error_and_logs_on_crm_error(
    order_factory,
    fulfillment_parameters_factory,
    mock_crm_client,
    ticket_manager,
    caplog,
):
    order = order_factory(fulfillment_parameters=fulfillment_parameters_factory())
    context = PurchaseContext.from_order_data(order)
    mock_crm_client.return_value.create_service_request.side_effect = CRMError("CRM API error")

    with pytest.raises(UnexpectedStopError) as exc_info:
        ticket_manager.create_new_ticket(context, "summary")

    assert exc_info.value.title == "Error creating Test Ticket ticket"
    assert "Error details: CRMError: CRM API error" in exc_info.value.message
    assert exc_info.value.__cause__ is not None
    assert "Failed to create Test Ticket ticket" in caplog.text


def test_has_open_ticket_returns_false_when_no_ticket_id(
    order_factory,
    fulfillment_parameters_factory,
    mocker,
    ticket_manager,
):
    order = order_factory(fulfillment_parameters=fulfillment_parameters_factory())
    context = PurchaseContext.from_order_data(order)
    mocker.patch(
        "swo_aws_extension.flows.steps.crm_tickets.ticket_manager.get_crm_customer_role_ticket_id",
        return_value=None,
    )

    result = ticket_manager.has_open_ticket(context)

    assert result is False


def test_has_open_ticket_returns_true_when_ticket_not_resolved(
    order_factory,
    fulfillment_parameters_factory,
    mock_crm_client,
    mocker,
    ticket_manager,
    caplog,
):
    ticket_state = {"state": "Open"}
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            crm_customer_role_ticket_id="TICKET-123",
        )
    )
    context = PurchaseContext.from_order_data(order)
    mocker.patch(
        "swo_aws_extension.flows.steps.crm_tickets.ticket_manager.get_crm_customer_role_ticket_id",
        return_value="TICKET-123",
    )
    mock_crm_client.return_value.get_service_request.return_value = ticket_state

    result = ticket_manager.has_open_ticket(context)

    assert result is True
    mock_crm_client.return_value.get_service_request.assert_called_once_with(
        context.order_id, "TICKET-123"
    )
    assert "Customer role ticket TICKET-123 is still open" in caplog.text


def test_has_open_ticket_returns_false_when_ticket_resolved(
    order_factory,
    fulfillment_parameters_factory,
    mock_crm_client,
    mocker,
    ticket_manager,
    caplog,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            crm_customer_role_ticket_id="TICKET-123",
        )
    )
    context = PurchaseContext.from_order_data(order)
    mocker.patch(
        "swo_aws_extension.flows.steps.crm_tickets.ticket_manager.get_crm_customer_role_ticket_id",
        return_value="TICKET-123",
    )
    mock_crm_client.return_value.get_service_request.return_value = {
        "state": CRM_TICKET_RESOLVED_STATE,
    }

    result = ticket_manager.has_open_ticket(context)

    assert result is False
    mock_crm_client.return_value.get_service_request.assert_called_once_with(
        context.order_id, "TICKET-123"
    )
    assert "Ticket with id TICKET-123 is closed, creating new ticket" in caplog.text
