import pytest
from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.aws.errors import AWSHttpError
from swo_aws_extension.constants import (
    HTTP_STATUS_INTERNAL_SERVER_ERROR,
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
    mock_purchase_new = mocker.patch(
        "swo_aws_extension.flows.fulfillment.base.purchase_existing_aws_environment.run"
    )
    new_order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_AWS_ENVIRONMENT.value
        ),
    )
    context = InitialAWSContext.from_order_data(new_order)

    fulfill_order(mocker.MagicMock(spec=MPTClient), context)  # act

    mock_purchase_new.assert_called_once()


def test_fulfill_order_exception(mocker, mpt_error_factory, order_factory):
    error_data = mpt_error_factory(
        HTTP_STATUS_INTERNAL_SERVER_ERROR, "Internal Server Error", "Error!"
    )
    error = AWSHttpError(HTTP_STATUS_INTERNAL_SERVER_ERROR, error_data)
    mocker.patch("swo_aws_extension.flows.fulfillment.base.notify_unhandled_exception_in_teams")
    mocker.patch(
        "swo_aws_extension.flows.fulfillment.base.purchase_new_aws_environment.run",
        side_effect=error,
    )
    new_order = order_factory()
    context = InitialAWSContext.from_order_data(new_order)

    with pytest.raises(AWSHttpError):
        fulfill_order(mocker.MagicMock(spec=MPTClient), context)


def test_setup_contexts(mpt_client, order_factory, agreement_factory):
    orders = [order_factory()]

    result = setup_contexts(mpt_client, orders)

    assert result[0].order == orders[0]
