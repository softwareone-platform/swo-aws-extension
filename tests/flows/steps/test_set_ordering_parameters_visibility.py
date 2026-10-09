import pytest
from mpt_extension_sdk.flows.pipeline import Step
from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.constants import MigrationOrderEnum, OrderParametersEnum, PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.set_ordering_parameters_visibility import (
    SetOrderingParametersVisibility,
)
from swo_aws_extension.parameters import get_ordering_parameter

MODULE = "swo_aws_extension.flows.steps.set_ordering_parameters_visibility"


@pytest.fixture
def migration_context(
    order_factory, order_parameters_factory, fulfillment_parameters_factory, dummy_constraints
):
    def factory(phase=PhasesEnum.CREATE_BILLING_TRANSFER_INVITATION.value, constraints=None):
        order_parameters = order_parameters_factory(
            migration=MigrationOrderEnum.YES.value, constraints=constraints
        )
        account_type = next(
            parameter
            for parameter in order_parameters
            if parameter["externalId"] == OrderParametersEnum.ACCOUNT_TYPE
        )
        account_type["constraints"] = (constraints or dummy_constraints).copy()
        order = order_factory(
            order_parameters=order_parameters,
            fulfillment_parameters=fulfillment_parameters_factory(phase=phase),
        )
        return PurchaseContext.from_order_data(order)

    return factory


def fake_update_order(_client, order_id, **kwargs):
    return {"id": order_id, "parameters": kwargs["parameters"]}


@pytest.fixture
def mock_update_order(mocker):
    return mocker.patch(f"{MODULE}.update_order", side_effect=fake_update_order)


def test_sets_ordering_parameters_visible(mocker, migration_context, mock_update_order):
    mock_client = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    context = migration_context()
    step = SetOrderingParametersVisibility()

    step(mock_client, context, next_step_mock)  # act

    for external_id in (
        OrderParametersEnum.ACCOUNT_TYPE,
        OrderParametersEnum.MASTER_PAYER_ACCOUNT_ID,
        OrderParametersEnum.SUPPORT_TYPE,
        OrderParametersEnum.CONTACT,
    ):
        assert get_ordering_parameter(external_id, context.order)["constraints"]["hidden"] is False
    is_migration = get_ordering_parameter(OrderParametersEnum.IS_MIGRATION, context.order)
    assert is_migration["constraints"]["hidden"] is True
    mock_update_order.assert_called_once_with(
        mock_client, context.order_id, parameters=context.order["parameters"]
    )
    next_step_mock.assert_called_once_with(mock_client, context)


def test_keeps_other_constraints(mocker, migration_context, mock_update_order):
    mock_client = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    context = migration_context(constraints={"hidden": True, "readonly": True, "required": True})
    step = SetOrderingParametersVisibility()

    step(mock_client, context, next_step_mock)  # act

    support_type = get_ordering_parameter(OrderParametersEnum.SUPPORT_TYPE, context.order)
    assert support_type["constraints"] == {"hidden": False, "readonly": True, "required": True}


def test_skips_when_parameters_already_visible(mocker, migration_context, mock_update_order):
    mock_client = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    context = migration_context(constraints={"hidden": False, "readonly": False, "required": False})
    step = SetOrderingParametersVisibility()

    step(mock_client, context, next_step_mock)  # act

    mock_update_order.assert_not_called()
    next_step_mock.assert_called_once_with(mock_client, context)


def test_skips_when_phase_does_not_match(mocker, migration_context, mock_update_order):
    mock_client = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    context = migration_context(phase=PhasesEnum.CREATE_SUBSCRIPTION.value)
    step = SetOrderingParametersVisibility()

    step(mock_client, context, next_step_mock)  # act

    mock_update_order.assert_not_called()
    next_step_mock.assert_called_once_with(mock_client, context)
