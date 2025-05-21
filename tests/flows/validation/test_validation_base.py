import pytest
from mpt_extension_sdk.flows.context import ORDER_TYPE_CHANGE, ORDER_TYPE_TERMINATION

from swo_aws_extension.aws.errors import AWSHttpError
from swo_aws_extension.flows.error import strip_trace_id
from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.validation import validate_order


def test_validate_purchase_order_exception(mocker, mpt_error_factory, order_factory):
    error_data = mpt_error_factory(500, "Internal Server Error", "Oops!")
    error = AWSHttpError(500, error_data)
    mocked_notify = mocker.patch(
        "swo_aws_extension.flows.validation.base.notify_unhandled_exception_in_teams"
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.base.validate_purchase_order",
        side_effect=error,
    )

    order = order_factory()
    context = InitialAWSContext.from_order_data(order)
    with pytest.raises(AWSHttpError):
        validate_order(mocker.MagicMock(), context)

    process, order_id, tb = mocked_notify.mock_calls[0].args
    assert process == "validation"
    assert order_id == order["id"]
    assert strip_trace_id(str(error)) in tb


def test_validation_change_order(mocker, mpt_client, order_factory):
    order = order_factory(order_type=ORDER_TYPE_CHANGE)
    mock_validate_and_setup_change_order = mocker.patch(
        "swo_aws_extension.flows.validation.base.validate_and_setup_change_order",
        return_value=[False, order],
    )

    context = InitialAWSContext.from_order_data(order)
    result = validate_order(mpt_client, context)
    assert result == order
    mock_validate_and_setup_change_order.assert_called_once_with(mpt_client, context)


def test_validation_termination_order(mocker, mpt_client, order_factory):
    order = order_factory(order_type=ORDER_TYPE_TERMINATION)
    context = InitialAWSContext.from_order_data(order)
    result = validate_order(mpt_client, context)
    assert result == order
