import pytest

from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.crm_tickets.terminate_order import CRMTicketTerminateOrder
from swo_aws_extension.flows.steps.errors import SkipStepError
from swo_aws_extension.parameters import get_crm_terminate_order_ticket_id


def test_pre_step_skips_when_ticket_exists(order_factory, fulfillment_parameters_factory, config):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            crm_terminate_order_ticket_id="TICKET-123",
        )
    )
    context = PurchaseContext.from_order_data(order)

    with pytest.raises(SkipStepError) as exc_info:
        CRMTicketTerminateOrder(config).pre_step(context)

    assert "CRM Terminate Order Ticket is already created" in str(exc_info.value)


def test_pre_step_proceeds_when_no_ticket(order_factory, fulfillment_parameters_factory, config):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            crm_terminate_order_ticket_id="",
        )
    )
    context = PurchaseContext.from_order_data(order)

    CRMTicketTerminateOrder(config).pre_step(context)  # act

    assert context.order is not None


def test_process_creates_service_request(
    order_factory,
    fulfillment_parameters_factory,
    mpt_client,
    mock_crm_client,
    config,
    buyer,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(),
    )
    context = PurchaseContext.from_order_data(order)
    context.buyer = buyer
    mock_crm_client.return_value.create_service_request.return_value = {"id": "TICKET-123"}

    CRMTicketTerminateOrder(config).process(mpt_client, context)  # act

    assert mock_crm_client.return_value.create_service_request.called


def test_process_sets_ticket_id_on_success(
    order_factory,
    fulfillment_parameters_factory,
    mpt_client,
    mock_crm_client,
    config,
    buyer,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            crm_terminate_order_ticket_id="",
        )
    )
    context = PurchaseContext.from_order_data(order)
    context.buyer = buyer
    mock_crm_client.return_value.create_service_request.return_value = {"id": "TICKET-456"}

    CRMTicketTerminateOrder(config).process(mpt_client, context)  # act

    assert get_crm_terminate_order_ticket_id(context.order) == "TICKET-456"


def test_process_logs_ticket_creation(
    order_factory,
    fulfillment_parameters_factory,
    mpt_client,
    mock_crm_client,
    config,
    buyer,
    caplog,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            crm_terminate_order_ticket_id="",
        )
    )
    context = PurchaseContext.from_order_data(order)
    context.buyer = buyer
    mock_crm_client.return_value.create_service_request.return_value = {"id": "TICKET-456"}

    CRMTicketTerminateOrder(config).process(mpt_client, context)  # act

    assert "Terminate Order ticket created with ID TICKET-456" in caplog.text


def test_process_logs_no_ticket_id_returned(
    order_factory,
    fulfillment_parameters_factory,
    mpt_client,
    mock_crm_client,
    config,
    buyer,
    caplog,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            crm_terminate_order_ticket_id="",
        )
    )
    context = PurchaseContext.from_order_data(order)
    context.buyer = buyer
    mock_crm_client.return_value.create_service_request.return_value = {}

    CRMTicketTerminateOrder(config).process(mpt_client, context)  # act

    assert "No ticket ID returned from CRM" in caplog.text
