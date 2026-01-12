from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.constants import (
    AccountTypesEnum,
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


def test_fulfill_unsupported_order_type(mpt_client, order_factory, caplog):
    unsupported_order = order_factory(
        order_id="ORD-UNSUP",
        order_type="Change",
    )
    context = InitialAWSContext.from_order_data(unsupported_order)

    fulfill_order(mpt_client, context)  # act

    assert "ORD-UNSUP - Unsupported order type: Change" in caplog.text


def test_setup_contexts(mpt_client, order_factory):
    orders = [order_factory()]

    result = setup_contexts(mpt_client, orders)

    assert result[0].order == orders[0]
