from mpt_extension_sdk.flows.context import (
    ORDER_TYPE_CHANGE,
)
from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.constants import (
    OrderCompletedTemplateEnum,
    PhasesEnum,
)
from swo_aws_extension.flows.order import (
    ChangeContext,
    InitialAWSContext,
)
from swo_aws_extension.flows.steps import (
    CompleteChangeOrderStep,
    CompleteOrderStep,
    CompletePurchaseOrderStep,
)


def test_complete_order(
    mocker,
    order_factory,
    config,
    aws_client_factory,
    fulfillment_parameters_factory,
    mock_switch_order_status_to_complete,
):
    order = order_factory(fulfillment_parameters=fulfillment_parameters_factory(phase=""))
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")

    context = InitialAWSContext.from_order_data(order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()

    complete_order = CompleteOrderStep()
    complete_order(mpt_client_mock, context, next_step_mock)

    mock_switch_order_status_to_complete.assert_called_once_with(
        mpt_client_mock,
        OrderCompletedTemplateEnum.NEW_ACCOUNT_WITH_PLS.value,
    )
    next_step_mock.assert_called_once_with(mpt_client_mock, context)


def test_complete_purchase_order_phase(
    mocker,
    order_factory,
    config,
    aws_client_factory,
    fulfillment_parameters_factory,
    mock_switch_order_status_to_complete,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.COMPLETED.value)
    )
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")

    context = InitialAWSContext.from_order_data(order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()
    complete_order = CompletePurchaseOrderStep()
    complete_order(mpt_client_mock, context, next_step_mock)

    mock_switch_order_status_to_complete.assert_called_once_with(
        mpt_client_mock,
        OrderCompletedTemplateEnum.NEW_ACCOUNT_WITH_PLS.value,
    )

    next_step_mock.assert_called_once_with(mpt_client_mock, context)


def test_complete_purchase_order_phase_invalid_phase(
    mocker, order_factory, config, aws_client_factory, fulfillment_parameters_factory
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.PRECONFIGURATION_MPA.value
        )
    )
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")

    context = InitialAWSContext.from_order_data(order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()

    complete_order = CompletePurchaseOrderStep()
    complete_order(mpt_client_mock, context, next_step_mock)

    next_step_mock.assert_called_once_with(mpt_client_mock, context)


def test_complete_change_order(
    mocker,
    order_factory,
    config,
    aws_client_factory,
    fulfillment_parameters_factory,
    mock_switch_order_status_to_complete,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=""),
        order_type=ORDER_TYPE_CHANGE,
    )
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")

    context = ChangeContext.from_order_data(order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()

    complete_order = CompleteChangeOrderStep()
    complete_order(mpt_client_mock, context, next_step_mock)
    mock_switch_order_status_to_complete.assert_called_once_with(
        mpt_client_mock, OrderCompletedTemplateEnum.CHANGE.value
    )

    next_step_mock.assert_called_once_with(mpt_client_mock, context)
