from swo_aws_extension.constants import AccountTypesEnum
from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.steps.complete_order import CompleteTerminationOrder


def test_pre_step_logs_start(order_factory, caplog):
    order = order_factory()
    context = InitialAWSContext.from_order_data(order)
    step = CompleteTerminationOrder()

    step.pre_step(context)  # act

    assert caplog.messages == [
        "ORD-0792-5000-2253-4210 - Next - Starting Terminate order completion step"
    ]


def test_process_new_account(mocker, order_factory, order_parameters_factory, mpt_client):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.NEW_AWS_ENVIRONMENT.value
        ),
    )
    mock_switch = mocker.patch(
        "swo_aws_extension.flows.steps.complete_order.switch_order_status_to_complete"
    )
    context = InitialAWSContext.from_order_data(order)
    step = CompleteTerminationOrder()

    step.process(mpt_client, context)  # act

    mock_switch.assert_called_once()


def test_process_existing_account(mocker, order_factory, order_parameters_factory, mpt_client):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_AWS_ENVIRONMENT.value
        ),
    )
    mock_switch = mocker.patch(
        "swo_aws_extension.flows.steps.complete_order.switch_order_status_to_complete"
    )
    context = InitialAWSContext.from_order_data(order)
    step = CompleteTerminationOrder()

    step.process(mpt_client, context)  # act

    mock_switch.assert_called_once()


def test_post_step_call(order_factory, order_parameters_factory, mpt_client, caplog):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.NEW_AWS_ENVIRONMENT.value
        ),
    )
    context = InitialAWSContext.from_order_data(order)
    step = CompleteTerminationOrder()

    step.post_step(mpt_client, context)  # act

    assert caplog.messages == [
        "ORD-0792-5000-2253-4210 - Completed - Termination order has been completed successfully"
    ]
