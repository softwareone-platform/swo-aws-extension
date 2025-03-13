import pytest

from swo_aws_extension.aws.errors import AWSHttpError
from swo_aws_extension.flows.error import strip_trace_id
from swo_aws_extension.flows.fulfillment import fulfill_order


def test_fulfill_order_exception(mocker, mpt_error_factory, order_factory):
    error_data = mpt_error_factory(500, "Internal Server Error", "Oops!")
    error = AWSHttpError(500, error_data)
    mocked_notify = mocker.patch(
        "swo_aws_extension.flows.fulfillment.base.notify_unhandled_exception_in_teams"
    )
    mocker.patch(
        "swo_aws_extension.flows.fulfillment.base.purchase.run",
        side_effect=error,
    )

    order = order_factory(order_id="ORD-FFFF")
    with pytest.raises(AWSHttpError):
        fulfill_order(mocker.MagicMock(), order)

    process, order_id, tb = mocked_notify.mock_calls[0].args
    assert process == "fulfillment"
    assert order_id == order["id"]
    assert strip_trace_id(str(error)) in tb
