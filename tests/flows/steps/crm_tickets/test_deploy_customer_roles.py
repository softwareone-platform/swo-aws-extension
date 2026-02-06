import pytest

from swo_aws_extension.constants import CRM_TICKET_RESOLVED_STATE, PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.crm_tickets.deploy_customer_roles import (
    CRMTicketDeployCustomerRoles,
)
from swo_aws_extension.flows.steps.crm_tickets.templates.deploy_roles import DEPLOY_ROLES_TEMPLATE
from swo_aws_extension.flows.steps.errors import SkipStepError, UnexpectedStopError
from swo_aws_extension.parameters import (
    get_crm_customer_role_ticket_id,
    get_formatted_technical_contact,
    get_mpa_account_id,
)
from swo_aws_extension.swo.cloud_orchestrator.errors import CloudOrchestratorError
from swo_aws_extension.swo.crm_service.client import ServiceRequest
from swo_aws_extension.swo.crm_service.errors import CRMError


@pytest.fixture
def mock_cloud_orchestrator_client(mocker):
    return mocker.patch(
        "swo_aws_extension.flows.steps.crm_tickets.deploy_customer_roles.CloudOrchestratorClient"
    )


@pytest.fixture
def mock_deploy_roles_crm_client(mocker):
    return mocker.patch(
        "swo_aws_extension.flows.steps.crm_tickets.deploy_customer_roles.get_service_client"
    )


def test_pre_step_skips_wrong_phase(order_factory, fulfillment_parameters_factory, config):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_NEW_AWS_ENVIRONMENT.value
        )
    )
    context = PurchaseContext.from_order_data(order)

    with pytest.raises(SkipStepError):
        CRMTicketDeployCustomerRoles(config).pre_step(context)


def test_pre_step_skips_when_ticket_is_open(
    order_factory,
    fulfillment_parameters_factory,
    mock_crm_client,
    config,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CUSTOMER_ROLES.value,
            crm_customer_role_ticket_id="EXISTING-TICKET",
        )
    )
    context = PurchaseContext.from_order_data(order)
    mock_crm_client.return_value.get_service_request.return_value = {"state": "Open"}

    with pytest.raises(SkipStepError):
        CRMTicketDeployCustomerRoles(config).pre_step(context)


def test_pre_step_skips_roles_deployed(
    order_factory,
    fulfillment_parameters_factory,
    mock_cloud_orchestrator_client,
    config,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CUSTOMER_ROLES.value,
        )
    )
    context = PurchaseContext.from_order_data(order)
    mock_cloud_orchestrator_client.return_value.get_bootstrap_role_status.return_value = {
        "deployed": True,
        "message": "Roles are deployed",
    }

    with pytest.raises(SkipStepError):
        CRMTicketDeployCustomerRoles(config).pre_step(context)


def test_pre_step_skips_cached_status_deployed(
    order_factory,
    fulfillment_parameters_factory,
    mock_cloud_orchestrator_client,
    config,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CUSTOMER_ROLES.value,
        )
    )
    context = PurchaseContext.from_order_data(order)
    context.bootstrap_roles_status = {"deployed": True, "message": "Cached status"}

    with pytest.raises(SkipStepError):
        CRMTicketDeployCustomerRoles(config).pre_step(context)

    mock_cloud_orchestrator_client.return_value.get_bootstrap_role_status.assert_not_called()


def test_pre_step_proceeds_roles_not_deployed(
    order_factory,
    fulfillment_parameters_factory,
    mock_cloud_orchestrator_client,
    config,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CUSTOMER_ROLES.value,
        )
    )
    context = PurchaseContext.from_order_data(order)
    mock_cloud_orchestrator_client.return_value.get_bootstrap_role_status.return_value = {
        "deployed": False,
        "message": "Roles not deployed",
    }

    result = CRMTicketDeployCustomerRoles(config).pre_step(context)

    assert result is None


def test_pre_step_proceeds_ticket_resolved(
    order_factory,
    fulfillment_parameters_factory,
    mock_crm_client,
    mock_cloud_orchestrator_client,
    config,
    caplog,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CUSTOMER_ROLES.value,
            crm_customer_role_ticket_id="RESOLVED-TICKET",
        )
    )
    context = PurchaseContext.from_order_data(order)
    mock_crm_client.return_value.get_service_request.return_value = {
        "state": CRM_TICKET_RESOLVED_STATE
    }
    mock_cloud_orchestrator_client.return_value.get_bootstrap_role_status.return_value = {
        "deployed": False,
        "message": "Roles not deployed",
    }

    CRMTicketDeployCustomerRoles(config).pre_step(context)  # act

    assert "is closed, creating new ticket" in caplog.text


def test_pre_step_error_on_orchestrator_failure(
    order_factory,
    fulfillment_parameters_factory,
    mock_cloud_orchestrator_client,
    config,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CUSTOMER_ROLES.value,
        )
    )
    context = PurchaseContext.from_order_data(order)
    mock_cloud_orchestrator_client.return_value.get_bootstrap_role_status.side_effect = (
        CloudOrchestratorError("API error")
    )

    with pytest.raises(UnexpectedStopError) as error:
        CRMTicketDeployCustomerRoles(config).pre_step(context)

    assert "Error checking customer roles" in error.value.title


def test_process_creates_ticket_successfully(
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
            phase=PhasesEnum.CHECK_CUSTOMER_ROLES.value,
        )
    )
    context = PurchaseContext.from_order_data(order)
    context.buyer = buyer
    mock_crm_client.return_value.create_service_request.return_value = {"id": "TICKET-123"}

    CRMTicketDeployCustomerRoles(config).process(mpt_client, context)  # act

    # Verify service request was created with correct parameters
    contact = get_formatted_technical_contact(context.order)
    expected_service_request = ServiceRequest(
        additional_info=DEPLOY_ROLES_TEMPLATE.additional_info,
        summary=DEPLOY_ROLES_TEMPLATE.summary.format(
            customer_name=context.buyer.get("name"),
            buyer_id=context.buyer.get("id"),
            buyer_external_id=context.buyer.get("externalIds", {}).get("erpCustomer", ""),
            seller_country=context.seller.get("address", {}).get("country", ""),
            pm_account_id=context.pm_account_id,
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
    # Verify ticket ID is stored
    assert get_crm_customer_role_ticket_id(context.order) == "TICKET-123"
    # Verify logging
    assert "Deploy Customer Roles ticket created with ID TICKET-123" in caplog.text


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
            phase=PhasesEnum.CHECK_CUSTOMER_ROLES.value,
        )
    )
    context = PurchaseContext.from_order_data(order)
    context.buyer = buyer
    mock_crm_client.return_value.create_service_request.return_value = {"status": "created"}

    CRMTicketDeployCustomerRoles(config).process(mpt_client, context)  # act

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
            phase=PhasesEnum.CHECK_CUSTOMER_ROLES.value,
        )
    )
    context = PurchaseContext.from_order_data(order)
    context.buyer = buyer
    mock_crm_client.return_value.create_service_request.side_effect = CRMError("CRM API error")

    with pytest.raises(UnexpectedStopError) as error:
        CRMTicketDeployCustomerRoles(config).process(mpt_client, context)

    assert "Error creating Deploy Customer Roles ticket" in error.value.title


def test_post_step_updates_order(
    mocker, order_factory, fulfillment_parameters_factory, mpt_client, config
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CUSTOMER_ROLES.value,
        )
    )
    context = PurchaseContext.from_order_data(order)
    mock_update = mocker.patch(
        "swo_aws_extension.flows.steps.crm_tickets.base.update_order",
        return_value=order,
    )

    CRMTicketDeployCustomerRoles(config).post_step(mpt_client, context)  # act

    mock_update.assert_called_once_with(
        mpt_client, context.order_id, parameters=context.order["parameters"]
    )
