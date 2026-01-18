import pytest

from swo_aws_extension.constants import AccountTypesEnum, OrderCompletedTemplate, PhasesEnum
from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.steps.complete_order import CompleteOrder, CompleteTerminationOrder
from swo_aws_extension.flows.steps.errors import SkipStepError


@pytest.fixture
def initial_context(order_factory):
    def factory(order=None):
        if order is None:
            order = order_factory()
        return InitialAWSContext.from_order_data(order)

    return factory


def test_complete_order_pre_step_skips(
    order_factory, fulfillment_parameters_factory, initial_context, config
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_NEW_AWS_ENVIRONMENT.value
        )
    )
    context = initial_context(order)
    step = CompleteOrder(config)

    with pytest.raises(SkipStepError):
        step.pre_step(context)


def test_complete_order_pre_step_proceeds(
    order_factory, fulfillment_parameters_factory, initial_context, config
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.COMPLETED.value)
    )
    context = initial_context(order)
    step = CompleteOrder(config)

    step.pre_step(context)  # act

    assert context.order is not None


def test_complete_order_process_completed(
    mocker, order_factory, order_parameters_factory, mpt_client, initial_context, config
):
    order = order_factory()
    mock_switch = mocker.patch(
        "swo_aws_extension.flows.steps.complete_order.switch_order_status_to_complete_and_notify"
    )
    mocker.patch("swo_aws_extension.flows.steps.complete_order.update_agreement")
    context = initial_context(order)
    step = CompleteOrder(config)

    step.process(mpt_client, context)  # act

    mock_switch.assert_called_once_with(mpt_client, context, OrderCompletedTemplate.PURCHASE)


def test_complete_order_post_step_logs(order_factory, mpt_client, caplog, initial_context, config):
    order = order_factory()
    context = initial_context(order)
    step = CompleteOrder(config)

    step.post_step(mpt_client, context)  # act

    assert (
        "ORD-0792-5000-2253-4210 - Completed - order has been completed successfully" in caplog.text
    )


def test_termination_pre_step_logs_start(order_factory, caplog, initial_context, config):
    order = order_factory()
    context = initial_context(order)
    step = CompleteTerminationOrder(config)

    step.pre_step(context)  # act

    assert caplog.messages == [
        "ORD-0792-5000-2253-4210 - Next - Starting Terminate order completion step"
    ]


def test_termination_process(
    mocker, order_factory, order_parameters_factory, mpt_client, initial_context, config
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.NEW_AWS_ENVIRONMENT.value
        ),
    )
    mock_switch = mocker.patch(
        "swo_aws_extension.flows.steps.complete_order.switch_order_status_to_complete_and_notify"
    )
    context = initial_context(order)
    step = CompleteTerminationOrder(config)

    step.process(mpt_client, context)  # act

    mock_switch.assert_called_once_with(mpt_client, context, OrderCompletedTemplate.TERMINATION)


def test_termination_post_step_logs(
    order_factory, order_parameters_factory, mpt_client, caplog, initial_context, config
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.NEW_AWS_ENVIRONMENT.value
        ),
    )
    context = initial_context(order)
    step = CompleteTerminationOrder(config)

    step.post_step(mpt_client, context)  # act

    assert caplog.messages == [
        "ORD-0792-5000-2253-4210 - Completed - Termination order has been completed successfully"
    ]
