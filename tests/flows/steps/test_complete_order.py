from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.order import ChangeContext, InitialAWSContext
from swo_aws_extension.flows.steps import CompleteChangeOrder, CompleteOrder, CompletePurchaseOrder


def test_complete_order(
    mocker, order_factory, config, aws_client_factory, fulfillment_parameters_factory
):
    order = order_factory(fulfillment_parameters=fulfillment_parameters_factory(phase=""))
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")

    context = InitialAWSContext(order=order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()
    mocked_get_product_template_or_default = mocker.patch(
        "swo_aws_extension.flows.steps.complete_order.get_product_template_or_default",
        return_value={"id": "TPL-964-112"},
    )
    mocked_complete_order = mocker.patch(
        "swo_aws_extension.flows.steps.complete_order.complete_order",
        return_value=order,
    )

    complete_order = CompleteOrder("template_name")
    complete_order(mpt_client_mock, context, next_step_mock)

    mocked_get_product_template_or_default.assert_called_once_with(
        mpt_client_mock, "PRD-1111-1111", "Completed", "template_name"
    )
    mocked_complete_order.assert_called_once_with(
        mpt_client_mock,
        context.order_id,
        {"id": "TPL-964-112"},
        parameters=context.order["parameters"],
    )

    next_step_mock.assert_called_once_with(mpt_client_mock, context)


def test_complete_purchase_order_phase(
    mocker, order_factory, config, aws_client_factory, fulfillment_parameters_factory
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.COMPLETED)
    )
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")

    context = InitialAWSContext(order=order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()
    mocked_get_product_template_or_default = mocker.patch(
        "swo_aws_extension.flows.steps.complete_order.get_product_template_or_default",
        return_value={"id": "TPL-964-112"},
    )
    mocked_complete_order = mocker.patch(
        "swo_aws_extension.flows.steps.complete_order.complete_order",
        return_value=order,
    )

    complete_order = CompletePurchaseOrder("template_name")
    complete_order(mpt_client_mock, context, next_step_mock)

    mocked_get_product_template_or_default.assert_called_once_with(
        mpt_client_mock, "PRD-1111-1111", "Completed", "template_name"
    )
    mocked_complete_order.assert_called_once_with(
        mpt_client_mock,
        context.order_id,
        {"id": "TPL-964-112"},
        parameters=context.order["parameters"],
    )

    next_step_mock.assert_called_once_with(mpt_client_mock, context)


def test_complete_purchase_order_phase_invalid_phase(
    mocker, order_factory, config, aws_client_factory, fulfillment_parameters_factory
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.PRECONFIGURATION_MPA)
    )
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")

    context = InitialAWSContext(order=order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()

    complete_order = CompletePurchaseOrder("template_name")
    complete_order(mpt_client_mock, context, next_step_mock)

    next_step_mock.assert_called_once_with(mpt_client_mock, context)


def test_complete_change_order(
    mocker, order_factory, config, aws_client_factory, fulfillment_parameters_factory
):
    order = order_factory(fulfillment_parameters=fulfillment_parameters_factory(phase=""))
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")

    context = ChangeContext(order=order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()
    mocked_get_product_template_or_default = mocker.patch(
        "swo_aws_extension.flows.steps.complete_order.get_product_template_or_default",
        return_value={"id": "TPL-964-112"},
    )
    mocked_complete_order = mocker.patch(
        "swo_aws_extension.flows.steps.complete_order.complete_order",
        return_value=order,
    )

    complete_order = CompleteChangeOrder("template_name")
    complete_order(mpt_client_mock, context, next_step_mock)

    mocked_get_product_template_or_default.assert_called_once_with(
        mpt_client_mock, "PRD-1111-1111", "Completed", "template_name"
    )
    mocked_complete_order.assert_called_once_with(
        mpt_client_mock,
        context.order_id,
        {"id": "TPL-964-112"},
        parameters=context.order["parameters"],
    )

    next_step_mock.assert_called_once_with(mpt_client_mock, context)
