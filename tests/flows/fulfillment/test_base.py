import pytest
from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.constants import (
    AccountTypesEnum,
    MigrationOrderEnum,
)
from swo_aws_extension.flows.fulfillment.base import fulfill_order, setup_contexts
from swo_aws_extension.flows.order import InitialAWSContext


def test_fulfill_new_aws_environment(
    mocker, mpt_error_factory, order_factory, order_parameters_factory
):
    mock_purchase_new = mocker.patch(
        "swo_aws_extension.flows.fulfillment.base.purchase_new_aws_environment.run"
    )
    new_order = order_factory(
        order_id="ORD-FFFF",
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.NEW_AWS_ENVIRONMENT.value
        ),
    )
    context = InitialAWSContext.from_order_data(new_order)

    fulfill_order(mocker.MagicMock(spec=MPTClient), context)  # act

    mock_purchase_new.assert_called_once()


def test_fulfill_existing_aws_environment(
    mocker, mpt_error_factory, order_factory, order_parameters_factory
):
    mock_purchase_existing = mocker.patch(
        "swo_aws_extension.flows.fulfillment.base.purchase_existing_aws_environment.run"
    )
    new_order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_AWS_ENVIRONMENT.value
        ),
    )
    context = InitialAWSContext.from_order_data(new_order)

    fulfill_order(mocker.MagicMock(spec=MPTClient), context)  # act

    mock_purchase_existing.assert_called_once()


@pytest.mark.parametrize(
    "account_type",
    [AccountTypesEnum.EXISTING_AWS_ENVIRONMENT.value, AccountTypesEnum.NEW_AWS_ENVIRONMENT.value],
)
def test_fulfill_migration_order_routes_to_migration_pipeline(
    mocker, order_factory, order_parameters_factory, account_type
):
    mock_purchase_migration = mocker.patch(
        "swo_aws_extension.flows.fulfillment.base.purchase_migration.run"
    )
    mock_purchase_new = mocker.patch(
        "swo_aws_extension.flows.fulfillment.base.purchase_new_aws_environment.run"
    )
    mock_purchase_existing = mocker.patch(
        "swo_aws_extension.flows.fulfillment.base.purchase_existing_aws_environment.run"
    )
    migration_order = order_factory(
        order_id="ORD-MIGR",
        order_parameters=order_parameters_factory(
            account_type=account_type,
            migration=MigrationOrderEnum.YES.value,
        ),
    )
    context = InitialAWSContext.from_order_data(migration_order)

    fulfill_order(mocker.MagicMock(spec=MPTClient), context)  # act

    mock_purchase_migration.assert_called_once()
    mock_purchase_new.assert_not_called()
    mock_purchase_existing.assert_not_called()


def test_fulfill_regular_order_does_not_use_migration_pipeline(
    mocker, order_factory, order_parameters_factory
):
    mock_purchase_migration = mocker.patch(
        "swo_aws_extension.flows.fulfillment.base.purchase_migration.run"
    )
    mock_purchase_existing = mocker.patch(
        "swo_aws_extension.flows.fulfillment.base.purchase_existing_aws_environment.run"
    )
    regular_order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_AWS_ENVIRONMENT.value,
            migration=MigrationOrderEnum.NO_MIGRATION.value,
        ),
    )
    context = InitialAWSContext.from_order_data(regular_order)

    fulfill_order(mocker.MagicMock(spec=MPTClient), context)  # act

    mock_purchase_existing.assert_called_once()
    mock_purchase_migration.assert_not_called()


def test_fulfill_termination_order(mocker, mpt_client, order_factory):
    mock_terminate = mocker.patch(
        "swo_aws_extension.flows.fulfillment.base.terminate.run", spec=True
    )
    termination_order = order_factory(
        order_type="Termination",
    )
    context = InitialAWSContext.from_order_data(termination_order)

    fulfill_order(mpt_client, context)  # act

    mock_terminate.assert_called_once()


@pytest.mark.parametrize("order_type", ["Change", "Unknown"])
def test_fulfill_unsupported_order_type_fails(mocker, order_factory, caplog, order_type):
    mock_fail = mocker.patch(
        "swo_aws_extension.flows.fulfillment.base.switch_order_status_to_failed"
    )
    order = order_factory(order_id="ORD-UNSUP", order_type=order_type)
    context = InitialAWSContext.from_order_data(order)

    fulfill_order(mocker.MagicMock(spec=MPTClient), context)  # act

    assert f"ORD-UNSUP - Order type {order_type} is not supported, failing order" in caplog.text
    mock_fail.assert_called_once_with(
        mocker.ANY,
        context,
        {
            "id": "AWS003",
            "message": f"Order type {order_type} is not supported by the AWS extension.",
        },
    )


def test_setup_contexts(mpt_client, order_factory):
    orders = [order_factory()]

    result = setup_contexts(mpt_client, orders)

    assert result[0].order == orders[0]
