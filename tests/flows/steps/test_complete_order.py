from swo_aws_extension.constants import AccountTypesEnum, OrderCompletedTemplate
from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.steps.complete_order import CompleteTerminationOrder


def test_pre_step_logs_start(order_factory):
    order = order_factory()
    context = InitialAWSContext.from_order_data(order)
    step = CompleteTerminationOrder()

    step.pre_step(context)  # act


def test_process_new_account(order_factory, order_parameters_factory):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.NEW_AWS_ENVIRONMENT.value
        ),
    )
    context = InitialAWSContext.from_order_data(order)
    step = CompleteTerminationOrder()

    step.process(context)  # act

    assert context.template == OrderCompletedTemplate.TERMINATION_NEW_ACCOUNT


def test_process_existing_account(order_factory, order_parameters_factory):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_AWS_ENVIRONMENT.value
        ),
    )
    context = InitialAWSContext.from_order_data(order)
    step = CompleteTerminationOrder()

    step.process(context)  # act

    assert context.template == OrderCompletedTemplate.TERMINATION_EXISTING_ACCOUNT


def test_post_step_calls_switch(mocker, order_factory, order_parameters_factory):
    mock_switch = mocker.patch(
        "swo_aws_extension.flows.steps.complete_order.switch_order_status_to_complete"
    )
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.NEW_AWS_ENVIRONMENT.value
        ),
    )
    context = InitialAWSContext.from_order_data(order)
    context.order["template"] = OrderCompletedTemplate.TERMINATION_NEW_ACCOUNT
    step = CompleteTerminationOrder()

    step.post_step(mocker.MagicMock(), context)  # act

    mock_switch.assert_called_once_with(
        mocker.ANY,
        context,
        OrderCompletedTemplate.TERMINATION_NEW_ACCOUNT,
    )
