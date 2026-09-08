import pytest
from mpt_extension_sdk.flows.pipeline import Step
from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.validate_migration_order import (
    ValidateMigrationOrder,
    get_missing_migration_data,
)


@pytest.fixture
def migration_order(order_factory, order_parameters_factory, fulfillment_parameters_factory):
    def factory(mpa_id="651706759263", support_type="resoldSupport", contact=None, cco="CCO-1"):
        return order_factory(
            order_parameters=order_parameters_factory(
                mpa_id=mpa_id, support_type=support_type, contact=contact
            ),
            fulfillment_parameters=fulfillment_parameters_factory(
                phase=PhasesEnum.CREATE_BILLING_TRANSFER_INVITATION.value,
                cco_contract_number=cco,
            ),
        )

    return factory


def test_get_missing_migration_data_returns_empty_when_complete(migration_order):
    order = migration_order()

    result = get_missing_migration_data(order)

    assert result == []


@pytest.mark.parametrize(
    ("order_kwargs", "expected_missing"),
    [
        ({"mpa_id": ""}, ["masterPayerID"]),
        ({"support_type": ""}, ["supportType"]),
        ({"contact": {}}, ["contact"]),
        ({"cco": ""}, ["ccoContractNumber"]),
        ({"mpa_id": "", "cco": ""}, ["masterPayerID", "ccoContractNumber"]),
    ],
)
def test_get_missing_migration_data_lists_empty_parameters(
    migration_order, order_kwargs, expected_missing
):
    order = migration_order(**order_kwargs)

    result = get_missing_migration_data(order)

    assert result == expected_missing


def test_get_missing_migration_data_reports_absent_parameters(
    order_factory, fulfillment_parameters_factory
):
    order = order_factory(
        order_parameters=[],
        fulfillment_parameters=fulfillment_parameters_factory(cco_contract_number="CCO-1"),
    )

    result = get_missing_migration_data(order)

    assert result == ["masterPayerID", "supportType", "contact"]


def test_validate_migration_order_proceeds_when_data_is_complete(mocker, migration_order):
    mock_client = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    mock_notify = mocker.patch("swo_aws_extension.flows.steps.base.notify_one_time_error")
    context = PurchaseContext.from_order_data(migration_order())
    step = ValidateMigrationOrder()

    step(mock_client, context, next_step_mock)  # act

    next_step_mock.assert_called_once_with(mock_client, context)
    mock_notify.assert_not_called()


def test_validate_migration_order_stops_and_notifies_when_data_is_missing(mocker, migration_order):
    mock_client = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    mock_notify = mocker.patch("swo_aws_extension.flows.steps.base.notify_one_time_error")
    order = migration_order(support_type="", cco="")
    context = PurchaseContext.from_order_data(order)
    step = ValidateMigrationOrder()

    step(mock_client, context, next_step_mock)  # act

    mock_notify.assert_called_once_with(
        f"Migration order {order['id']} is missing required data",
        f"The migration order {order['id']} cannot be processed because the following "
        "parameters have no value: supportType, ccoContractNumber. Please complete the order "
        "data in the marketplace so the fulfillment can continue.",
    )
    assert context.order.get("error") is None
    mock_client.assert_not_called()
    next_step_mock.assert_not_called()


def test_validate_migration_order_skips_when_phase_does_not_match(
    mocker, order_factory, fulfillment_parameters_factory
):
    mock_client = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    order = order_factory(
        order_parameters=[],
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_SUBSCRIPTION.value
        ),
    )
    context = PurchaseContext.from_order_data(order)
    step = ValidateMigrationOrder()

    step(mock_client, context, next_step_mock)  # act

    next_step_mock.assert_called_once_with(mock_client, context)
    assert context.order.get("error") is None
