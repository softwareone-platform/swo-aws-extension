from mpt_extension_sdk.flows.context import ORDER_TYPE_CHANGE

from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.validation.change import validate_and_setup_change_order


def test_validate_and_setup_change_order(mocker, mpt_client, aws_client_factory, order_factory):
    order = order_factory(order_type=ORDER_TYPE_CHANGE)
    context = InitialAWSContext.from_order_data(order)

    mock_step = mocker.patch(
        "swo_aws_extension.flows.validation.change.InitializeItemStep",
    )
    validate_and_setup_change_order(mpt_client, context)
    mock_step.assert_called_once()
