import pytest

from swo_aws_extension.constants import (
    CUSTOMER_ROLES_NOT_DEPLOYED_MESSAGE,
    CustomerRolesDeployed,
    FulfillmentParametersEnum,
    OrderQueryingTemplateEnum,
    PhasesEnum,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.check_customer_roles import CheckCustomerRoles
from swo_aws_extension.flows.steps.errors import (
    QueryStepError,
    SkipStepError,
    UnexpectedStopError,
)
from swo_aws_extension.parameters import (
    get_fulfillment_parameter,
    get_phase,
)
from swo_aws_extension.swo.cloud_orchestrator.errors import CloudOrchestratorError


@pytest.fixture
def mock_cloud_orchestrator_client(mocker):
    return mocker.patch(
        "swo_aws_extension.flows.steps.check_customer_roles.CloudOrchestratorClient"
    )


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
    mock_cloud_orchestrator_client,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CUSTOMER_ROLES,
        )
    )
    context = PurchaseContext.from_order_data(order)
    mock_cloud_orchestrator_client.return_value.get_bootstrap_role_status.return_value = {
        "deployed": True,
        "message": "Roles are deployed",
    }

    CheckCustomerRoles(config).process(mpt_client, context)  # act

    assert (
        get_fulfillment_parameter(
            FulfillmentParametersEnum.CUSTOMER_ROLES_DEPLOYED.value, context.order
        )["value"]
        == CustomerRolesDeployed.YES.value
    )


def test_process_uses_cached_bootstrap_status(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mpt_client,
    mock_cloud_orchestrator_client,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CUSTOMER_ROLES,
        )
    )
    context = PurchaseContext.from_order_data(order)
    context.bootstrap_roles_status = {"deployed": True, "message": "Cached status"}

    CheckCustomerRoles(config).process(mpt_client, context)  # act

    mock_cloud_orchestrator_client.return_value.get_bootstrap_role_status.assert_not_called()


def test_process_query_error_when_not_deployed(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mpt_client,
    mock_cloud_orchestrator_client,
    caplog,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CUSTOMER_ROLES,
        )
    )
    context = PurchaseContext.from_order_data(order)
    mock_cloud_orchestrator_client.return_value.get_bootstrap_role_status.return_value = {
        "deployed": False,
        "message": "Bootstrap role not found",
    }

    with pytest.raises(QueryStepError) as exc_info:
        CheckCustomerRoles(config).process(mpt_client, context)

    assert exc_info.value.message == CUSTOMER_ROLES_NOT_DEPLOYED_MESSAGE
    assert exc_info.value.template_id == OrderQueryingTemplateEnum.WAITING_FOR_CUSTOMER_ROLES
    assert (
        get_fulfillment_parameter(
            FulfillmentParametersEnum.CUSTOMER_ROLES_DEPLOYED.value, context.order
        )["value"]
        == CustomerRolesDeployed.NO_DEPLOYED.value
    )
    assert "Customer roles are NOT deployed" in caplog.text


def test_process_error_on_orchestrator_fails(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mpt_client,
    mock_cloud_orchestrator_client,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CUSTOMER_ROLES,
        )
    )
    context = PurchaseContext.from_order_data(order)
    mock_cloud_orchestrator_client.return_value.get_bootstrap_role_status.side_effect = (
        CloudOrchestratorError("API error")
    )

    with pytest.raises(UnexpectedStopError) as exc_info:
        CheckCustomerRoles(config).process(mpt_client, context)  # act

    assert "Error checking customer roles" in exc_info.value.title


def test_post_step_updates_phase(
    mocker, order_factory, fulfillment_parameters_factory, mpt_client, config
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CUSTOMER_ROLES,
        )
    )
    context = PurchaseContext.from_order_data(order)
    updated_order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.ONBOARD_SERVICES)
    )
    mock_update = mocker.patch(
        "swo_aws_extension.flows.steps.check_customer_roles.update_order",
        return_value=updated_order,
    )

    CheckCustomerRoles(config).post_step(mpt_client, context)  # act

    assert get_phase(context.order) == PhasesEnum.ONBOARD_SERVICES
    mock_update.assert_called_once_with(
        mpt_client, context.order_id, parameters=context.order["parameters"]
    )
