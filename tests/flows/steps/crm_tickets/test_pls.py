import pytest

from swo_aws_extension.constants import SupportTypesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.crm_tickets.pls import CRMTicketPLS
from swo_aws_extension.flows.steps.crm_tickets.templates.pls import PLS_TEMPLATE
from swo_aws_extension.flows.steps.errors import SkipStepError, UnexpectedStopError
from swo_aws_extension.parameters import (
    get_crm_pls_ticket_id,
    get_formatted_supplementary_services,
    get_formatted_technical_contact,
    get_mpa_account_id,
    get_support_type,
)
from swo_aws_extension.swo.crm_service.client import ServiceRequest
from swo_aws_extension.swo.crm_service.errors import CRMError


def test_pre_step_skips_not_partner_led(order_factory, order_parameters_factory, config):
    order = order_factory(
        order_parameters=order_parameters_factory(
            support_type=SupportTypesEnum.AWS_RESOLD_SUPPORT.value
        )
    )
    context = PurchaseContext.from_order_data(order)

    with pytest.raises(SkipStepError):
        CRMTicketPLS(config).pre_step(context)


def test_pre_step_skips_ticket_exists(
    order_factory, order_parameters_factory, fulfillment_parameters_factory, config
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            support_type=SupportTypesEnum.PARTNER_LED_SUPPORT.value
        ),
        fulfillment_parameters=fulfillment_parameters_factory(
            crm_pls_ticket_id="TICKET-123",
        ),
    )
    context = PurchaseContext.from_order_data(order)

    with pytest.raises(SkipStepError):
        CRMTicketPLS(config).pre_step(context)


def test_pre_step_proceeds_conditions_met(
    order_factory, order_parameters_factory, fulfillment_parameters_factory, config
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            support_type=SupportTypesEnum.PARTNER_LED_SUPPORT.value
        ),
        fulfillment_parameters=fulfillment_parameters_factory(
            crm_pls_ticket_id="",
        ),
    )
    context = PurchaseContext.from_order_data(order)

    CRMTicketPLS(config).pre_step(context)  # act

    assert context.order is not None


def test_process_creates_service_request(
    order_factory,
    order_parameters_factory,
    mpt_client,
    mock_crm_client,
    config,
    buyer,
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            support_type=SupportTypesEnum.PARTNER_LED_SUPPORT.value
        )
    )
    context = PurchaseContext.from_order_data(order)
    context.buyer = buyer
    mock_crm_client.return_value.create_service_request.return_value = {"id": "TICKET-123"}

    CRMTicketPLS(config).process(mpt_client, context)  # act

    contact = get_formatted_technical_contact(context.order)
    expected_service_request = ServiceRequest(
        additional_info=PLS_TEMPLATE.additional_info,
        summary=PLS_TEMPLATE.summary.format(
            customer_name=context.buyer.get("name"),
            buyer_id=context.buyer.get("id"),
            buyer_external_id=context.buyer.get("externalIds", {}).get("erpCustomer", ""),
            order_id=context.order_id,
            master_payer_id=get_mpa_account_id(context.order),
            technical_contact_name=contact["name"],
            technical_contact_email=contact["email"],
            technical_contact_phone=contact["phone"],
            support_type=get_support_type(context.order),
            supplementary_services=get_formatted_supplementary_services(context.order),
        ),
        title=PLS_TEMPLATE.title,
    )
    mock_crm_client.return_value.create_service_request.assert_called_once_with(
        context.order_id, expected_service_request
    )


def test_process_sets_ticket_id_on_success(
    order_factory,
    order_parameters_factory,
    mpt_client,
    mock_crm_client,
    config,
    buyer,
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            support_type=SupportTypesEnum.PARTNER_LED_SUPPORT.value
        )
    )
    context = PurchaseContext.from_order_data(order)
    context.buyer = buyer
    mock_crm_client.return_value.create_service_request.return_value = {"id": "TICKET-123"}

    CRMTicketPLS(config).process(mpt_client, context)  # act

    assert get_crm_pls_ticket_id(context.order) == "TICKET-123"


def test_process_logs_ticket_creation(
    order_factory,
    order_parameters_factory,
    mpt_client,
    mock_crm_client,
    config,
    buyer,
    caplog,
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            support_type=SupportTypesEnum.PARTNER_LED_SUPPORT.value
        )
    )
    context = PurchaseContext.from_order_data(order)
    context.buyer = buyer
    mock_crm_client.return_value.create_service_request.return_value = {"id": "TICKET-123"}

    CRMTicketPLS(config).process(mpt_client, context)  # act

    assert "PLS ticket created with ID TICKET-123" in caplog.text


def test_process_logs_no_ticket_id_returned(
    order_factory,
    order_parameters_factory,
    mpt_client,
    mock_crm_client,
    config,
    buyer,
    caplog,
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            support_type=SupportTypesEnum.PARTNER_LED_SUPPORT.value
        )
    )
    context = PurchaseContext.from_order_data(order)
    context.buyer = buyer
    mock_crm_client.return_value.create_service_request.return_value = {"status": "created"}

    CRMTicketPLS(config).process(mpt_client, context)  # act

    assert "No ticket ID returned from CRM" in caplog.text


def test_process_raises_error_when_crm_fails(
    order_factory,
    order_parameters_factory,
    mpt_client,
    mock_crm_client,
    config,
    buyer,
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            support_type=SupportTypesEnum.PARTNER_LED_SUPPORT.value
        )
    )
    context = PurchaseContext.from_order_data(order)
    context.buyer = buyer
    mock_crm_client.return_value.create_service_request.side_effect = CRMError("CRM API error")

    with pytest.raises(UnexpectedStopError) as error:
        CRMTicketPLS(config).process(mpt_client, context)

    assert "Error creating PLS ticket" in error.value.title


def test_post_step_updates_order(
    mocker, order_factory, order_parameters_factory, mpt_client, config
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            support_type=SupportTypesEnum.PARTNER_LED_SUPPORT.value
        )
    )
    context = PurchaseContext.from_order_data(order)
    mock_update = mocker.patch(
        "swo_aws_extension.flows.steps.crm_tickets.base.update_order",
        return_value=order,
    )

    CRMTicketPLS(config).post_step(mpt_client, context)  # act

    mock_update.assert_called_once_with(
        mpt_client, context.order_id, parameters=context.order["parameters"]
    )
