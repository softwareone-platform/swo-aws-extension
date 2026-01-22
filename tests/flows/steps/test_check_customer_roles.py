import pytest

from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.constants import (
    CRM_TICKET_RESOLVED_STATE,
    CustomerRolesDeployed,
    FulfillmentParametersEnum,
    PhasesEnum,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.check_customer_roles import CheckCustomerRoles
from swo_aws_extension.flows.steps.crm_tickets.templates.deploy_roles import DEPLOY_ROLES_TEMPLATE
from swo_aws_extension.flows.steps.errors import (
    QueryStepError,
    SkipStepError,
    UnexpectedStopError,
)
from swo_aws_extension.parameters import (
    get_crm_customer_role_ticket_id,
    get_formatted_technical_contact,
    get_fulfillment_parameter,
    get_mpa_account_id,
    get_phase,
)
from swo_aws_extension.swo.crm_service.client import ServiceRequest
from swo_aws_extension.swo.crm_service.errors import CRMError


@pytest.fixture
def mock_crm_client(mocker):
    return mocker.patch("swo_aws_extension.flows.steps.check_customer_roles.get_service_client")


@pytest.fixture
def mock_aws_client(mocker):
    return mocker.patch("swo_aws_extension.flows.steps.check_customer_roles.AWSClient")


def test_pre_step_skips_wrong_phase(order_factory, fulfillment_parameters_factory, config):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_NEW_AWS_ENVIRONMENT
        )
    )
    context = PurchaseContext.from_order_data(order)

    with pytest.raises(SkipStepError):
        CheckCustomerRoles(config).pre_step(context)


def test_pre_step_proceeds_when_phase_matches(
    order_factory, fulfillment_parameters_factory, config
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.CHECK_CUSTOMER_ROLES)
    )
    context = PurchaseContext.from_order_data(order)

    CheckCustomerRoles(config).pre_step(context)  # act

    assert context.order is not None


def test_process_succeeds_when_roles_deployed(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mpt_client,
    mock_aws_client,
    caplog,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CUSTOMER_ROLES,
        )
    )
    context = PurchaseContext.from_order_data(order)

    CheckCustomerRoles(config).process(mpt_client, context)  # act

    assert (
        get_fulfillment_parameter(
            FulfillmentParametersEnum.CUSTOMER_ROLES_DEPLOYED.value, context.order
        )["value"]
        == CustomerRolesDeployed.YES.value
    )


def test_process_creates_ticket_when_not_deployed(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mpt_client,
    mock_aws_client,
    mock_crm_client,
    buyer,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CUSTOMER_ROLES,
        )
    )
    context = PurchaseContext.from_order_data(order)
    context.buyer = buyer
    mock_aws_client.side_effect = AWSError("Role not found")
    mock_crm_client.return_value.create_service_request.return_value = {"id": "TICKET-123"}

    with pytest.raises(QueryStepError):
        CheckCustomerRoles(config).process(mpt_client, context)

    contact = get_formatted_technical_contact(context.order)
    expected_service_request = ServiceRequest(
        additional_info=DEPLOY_ROLES_TEMPLATE.additional_info,
        summary=DEPLOY_ROLES_TEMPLATE.summary.format(
            customer_name=context.buyer.get("name"),
            buyer_id=context.buyer.get("id"),
            buyer_external_id=context.buyer.get("externalIds", {}).get("erpCustomer", ""),
            order_id=context.order_id,
            master_payer_id=get_mpa_account_id(context.order),
            technical_contact_name=contact["name"],
            technical_contact_email=contact["email"],
            technical_contact_phone=contact["phone"],
        ),
        title=DEPLOY_ROLES_TEMPLATE.title,
    )
    mock_crm_client.return_value.create_service_request.assert_called_once_with(
        context.order_id, expected_service_request
    )
    assert get_crm_customer_role_ticket_id(context.order) == "TICKET-123"


def test_process_skips_ticket_creation_when_open(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mpt_client,
    mock_aws_client,
    mock_crm_client,
    caplog,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CUSTOMER_ROLES,
            crm_customer_role_ticket_id="EXISTING-TICKET",
        )
    )
    context = PurchaseContext.from_order_data(order)
    mock_aws_client.side_effect = AWSError("Role not found")
    mock_crm_client.return_value.get_service_request.return_value = {"state": "Open"}

    with pytest.raises(QueryStepError):
        CheckCustomerRoles(config).process(mpt_client, context)

    mock_crm_client.return_value.create_service_request.assert_not_called()
    assert "Customer role ticket EXISTING-TICKET is still open" in caplog.text


def test_process_creates_new_ticket_when_resolved(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mpt_client,
    mock_aws_client,
    mock_crm_client,
    buyer,
    caplog,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CUSTOMER_ROLES,
            crm_customer_role_ticket_id="RESOLVED-TICKET",
        )
    )
    context = PurchaseContext.from_order_data(order)
    context.buyer = buyer
    mock_aws_client.side_effect = AWSError("Role not found")
    mock_crm_client.return_value.get_service_request.return_value = {
        "state": CRM_TICKET_RESOLVED_STATE
    }
    mock_crm_client.return_value.create_service_request.return_value = {"id": "NEW-TICKET"}

    with pytest.raises(QueryStepError):
        CheckCustomerRoles(config).process(mpt_client, context)

    assert "Ticket with id RESOLVED-TICKET is closed, creating new ticket" in caplog.text
    mock_crm_client.return_value.create_service_request.assert_called_once()
    assert get_crm_customer_role_ticket_id(context.order) == "NEW-TICKET"


def test_process_raises_error_when_crm_fails(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mpt_client,
    mock_aws_client,
    mock_crm_client,
    buyer,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CUSTOMER_ROLES,
        )
    )
    context = PurchaseContext.from_order_data(order)
    context.buyer = buyer
    mock_aws_client.side_effect = AWSError("Role not found")
    mock_crm_client.return_value.create_service_request.side_effect = CRMError("CRM API error")

    with pytest.raises(UnexpectedStopError) as error:
        CheckCustomerRoles(config).process(mpt_client, context)

    assert "Error creating pending customer roles ticket" in error.value.title


def test_process_logs_when_no_ticket_id(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mpt_client,
    mock_aws_client,
    mock_crm_client,
    buyer,
    caplog,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CUSTOMER_ROLES,
        )
    )
    context = PurchaseContext.from_order_data(order)
    context.buyer = buyer
    mock_aws_client.side_effect = AWSError("Role not found")
    mock_crm_client.return_value.create_service_request.return_value = {"status": "created"}

    with pytest.raises(QueryStepError):
        CheckCustomerRoles(config).process(mpt_client, context)

    assert "No ticket ID returned from CRM" in caplog.text
    assert not get_crm_customer_role_ticket_id(context.order)


def test_post_step_updates_phase(
    mocker, order_factory, fulfillment_parameters_factory, mpt_client, config
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CUSTOMER_ROLES,
        )
    )
    context = PurchaseContext.from_order_data(order)
    step = CheckCustomerRoles(config)
    updated_order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.ONBOARD_SERVICES)
    )
    mock_update = mocker.patch(
        "swo_aws_extension.flows.steps.check_customer_roles.update_order",
        return_value=updated_order,
    )

    step.post_step(mpt_client, context)  # act

    assert get_phase(context.order) == PhasesEnum.ONBOARD_SERVICES
    mock_update.assert_called_once_with(
        mpt_client, context.order_id, parameters=context.order["parameters"]
    )
