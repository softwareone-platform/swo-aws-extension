import pytest

from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.crm_tickets.new_account import CRMTicketNewAccount
from swo_aws_extension.flows.steps.crm_tickets.templates.new_account import NEW_ACCOUNT_TEMPLATE
from swo_aws_extension.flows.steps.errors import SkipStepError, UnexpectedStopError
from swo_aws_extension.parameters import (
    get_crm_new_account_ticket_id,
    get_formatted_supplementary_services,
    get_formatted_technical_contact,
    get_order_account_email,
    get_order_account_name,
    get_support_type,
)
from swo_aws_extension.swo.crm_service.client import ServiceRequest
from swo_aws_extension.swo.crm_service.errors import CRMError


def test_pre_step_skips_wrong_phase(order_factory, fulfillment_parameters_factory, config):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_BILLING_TRANSFER_INVITATION.value
        )
    )
    context = PurchaseContext.from_order_data(order)

    with pytest.raises(SkipStepError):
        CRMTicketNewAccount(config).pre_step(context)


def test_pre_step_skips_ticket_exists(order_factory, fulfillment_parameters_factory, config):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_NEW_AWS_ENVIRONMENT.value,
            crm_new_account_ticket_id="Ticket123",
        )
    )
    context = PurchaseContext.from_order_data(order)

    with pytest.raises(SkipStepError):
        CRMTicketNewAccount(config).pre_step(context)


def test_pre_step_proceeds_conditions_met(order_factory, fulfillment_parameters_factory, config):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_NEW_AWS_ENVIRONMENT.value,
            crm_new_account_ticket_id="",
        )
    )
    context = PurchaseContext.from_order_data(order)

    CRMTicketNewAccount(config).pre_step(context)  # act

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
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_NEW_AWS_ENVIRONMENT.value,
        )
    )
    context = PurchaseContext.from_order_data(order)
    context.buyer = buyer
    mock_crm_client.return_value.create_service_request.return_value = {"id": "TICKET-123"}

    CRMTicketNewAccount(config).process(mpt_client, context)  # act

    contact = get_formatted_technical_contact(context.order)
    expected_service_request = ServiceRequest(
        additional_info=NEW_ACCOUNT_TEMPLATE.additional_info,
        summary=NEW_ACCOUNT_TEMPLATE.summary.format(
            customer_name=context.buyer.get("name"),
            buyer_id=context.buyer.get("id"),
            buyer_external_id=context.buyer.get("externalIds", {}).get("erpCustomer", ""),
            order_id=context.order_id,
            order_account_name=get_order_account_name(context.order),
            order_account_email=get_order_account_email(context.order),
            technical_contact_name=contact["name"],
            technical_contact_email=contact["email"],
            technical_contact_phone=contact["phone"],
            support_type=get_support_type(context.order),
            supplementary_services=get_formatted_supplementary_services(context.order),
        ),
        title=NEW_ACCOUNT_TEMPLATE.title,
    )
    mock_crm_client.return_value.create_service_request.assert_called_once_with(
        context.order_id, expected_service_request
    )


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
            phase=PhasesEnum.CREATE_NEW_AWS_ENVIRONMENT.value,
        )
    )
    context = PurchaseContext.from_order_data(order)
    context.buyer = buyer
    mock_crm_client.return_value.create_service_request.return_value = {"id": "TICKET-123"}

    CRMTicketNewAccount(config).process(mpt_client, context)  # act

    assert get_crm_new_account_ticket_id(context.order) == "TICKET-123"


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
            phase=PhasesEnum.CREATE_NEW_AWS_ENVIRONMENT.value,
        )
    )
    context = PurchaseContext.from_order_data(order)
    context.buyer = buyer
    mock_crm_client.return_value.create_service_request.return_value = {"id": "TICKET-123"}

    CRMTicketNewAccount(config).process(mpt_client, context)  # act

    assert "New Account ticket created with ID TICKET-123" in caplog.text


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
            phase=PhasesEnum.CREATE_NEW_AWS_ENVIRONMENT.value,
        )
    )
    context = PurchaseContext.from_order_data(order)
    context.buyer = buyer
    mock_crm_client.return_value.create_service_request.return_value = {"status": "created"}

    CRMTicketNewAccount(config).process(mpt_client, context)  # act

    assert "No ticket ID returned from CRM" in caplog.text


def test_process_raises_error_when_crm_fails(
    order_factory,
    fulfillment_parameters_factory,
    mpt_client,
    mock_crm_client,
    config,
    buyer,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_NEW_AWS_ENVIRONMENT.value,
        )
    )
    context = PurchaseContext.from_order_data(order)
    context.buyer = buyer
    mock_crm_client.return_value.create_service_request.side_effect = CRMError("CRM API error")

    with pytest.raises(UnexpectedStopError) as error:
        CRMTicketNewAccount(config).process(mpt_client, context)

    assert "Error creating New Account ticket" in error.value.title


def test_post_step_updates_order(
    mocker, order_factory, fulfillment_parameters_factory, mpt_client, config
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_NEW_AWS_ENVIRONMENT.value,
        )
    )
    context = PurchaseContext.from_order_data(order)
    mock_update = mocker.patch(
        "swo_aws_extension.flows.steps.crm_tickets.base.update_order",
        return_value=order,
    )

    CRMTicketNewAccount(config).post_step(mpt_client, context)  # act

    mock_update.assert_called_once_with(
        mpt_client, context.order_id, parameters=context.order["parameters"]
    )
