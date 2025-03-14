# tests/swo_aws_extension/flows/steps/test_create_service_crm_ticket.py

from unittest.mock import Mock, create_autospec

import pytest
from swo.mpt.client import MPTClient

from swo_aws_extension.flows.order import CloseAccountContext
from swo_aws_extension.flows.steps.create_service_crm_ticket import (
    CreateServiceRequestStep,
)
from swo_crm_service_client.client import CRMServiceClient, ServiceRequest


@pytest.fixture()
def crm_client():
    return Mock(spec=CRMServiceClient)

@pytest.fixture()
def service_request():
    return ServiceRequest(
        externalUserEmail="albert.sola@softwareone.com",
        externalUsername="albert.sola@softwareone.com",
        requester="Supplier.Portal",
        subService="Service Activation",
        globalacademicExtUserId="notapplicable",
        additionalInfo="additionalInfo",
        summary="This is a test",
        title="This is a test from AWS Extension",
        serviceType="MarketPlaceServiceActivation",
    )


@pytest.fixture()
def service_request_factory(service_request):
    return Mock(return_value=service_request)


@pytest.fixture()
def crm_ticket_id_saver() -> Mock:
    return Mock(return_value=None)


@pytest.fixture()
def create_service_crm_ticket_step(
        mocker,
        crm_client,
        service_request_factory,
        crm_ticket_id_saver
    ):
    mocker.patch(
        "swo_aws_extension.flows.steps.create_service_crm_ticket.get_service_client",
        return_value=crm_client
    )

    return CreateServiceRequestStep(
        service_request_factory,
        ticket_id_saver=crm_ticket_id_saver,
        criteria=None,
    )


@pytest.fixture()
def context():
    return create_autospec(CloseAccountContext, instance=True)


@pytest.fixture()
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
        crm_ticket_id_saver
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
        crm_ticket_id_saver
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


def test_create_service_crm_ticket_unexpected_response(
        create_service_crm_ticket_step,
        crm_client,
        service_request_factory,
        context,
        next_step,
        service_request,
        crm_ticket_id_saver
    ):

    client = Mock(spec=MPTClient)
    context.order_id = "ORD-0000-0000"  # Set the order_id to a string
    create_service_crm_ticket_step.criteria = lambda context: True
    crm_client.create_service_request.return_value = {"error": "An error happened"}
    with pytest.raises(ValueError):
        create_service_crm_ticket_step(client, context, next_step)
    crm_ticket_id_saver.assert_not_called()

