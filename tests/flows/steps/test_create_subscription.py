from swo.mpt.client import MPTClient

from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.steps import CreateSubscription


def test_create_subscription_phase_invalid_phase(
    mocker, order_factory, config, aws_client_factory, fulfillment_parameters_factory
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.PRECONFIGURATION_MPA
        )
    )
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")

    context = InitialAWSContext(order=order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()

    create_subscription = CreateSubscription()
    create_subscription(mpt_client_mock, context, next_step_mock)

    next_step_mock.assert_called_once_with(mpt_client_mock, context)


def test_create_subscription_phase(
    mocker,
    order_factory,
    config,
    aws_client_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
    subscription_factory,
    account_creation_status_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_SUBSCRIPTIONS
        ),
    )
    subscription = subscription_factory()
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")

    mocked_get_order_subscription = mocker.patch(
        "swo_aws_extension.flows.steps.create_subscription.get_order_subscription_by_external_id",
        return_value=None,
    )
    mocked_create_subscription = mocker.patch(
        "swo_aws_extension.flows.steps.create_subscription.create_subscription",
        return_value=subscription,
    )

    context = InitialAWSContext(order=order)
    context.aws_client = aws_client
    context.account_creation_status = account_creation_status_factory(
        account_id="account_id"
    )
    next_step_mock = mocker.Mock()

    create_subscription = CreateSubscription()
    create_subscription(mpt_client_mock, context, next_step_mock)

    mocked_get_order_subscription.assert_called_once_with(
        mpt_client_mock, context.order["id"], "account_id"
    )
    del subscription["id"]
    mocked_create_subscription.assert_called_once_with(
        mpt_client_mock, context.order_id, subscription
    )
    next_step_mock.assert_called_once_with(mpt_client_mock, context)


def test_create_subscription_phase_subscription_already_created(
    mocker,
    order_factory,
    config,
    aws_client_factory,
    fulfillment_parameters_factory,
    subscription_factory,
    order_parameters_factory,
    account_creation_status_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_SUBSCRIPTIONS
        ),
        order_parameters=order_parameters_factory(account_id=""),
    )
    subscription = subscription_factory()
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")

    context = InitialAWSContext(order=order)
    context.aws_client = aws_client
    context.account_creation_status = account_creation_status_factory(
        account_id="account_id"
    )
    next_step_mock = mocker.Mock()
    mocked_get_order_subscription = mocker.patch(
        "swo_aws_extension.flows.steps.create_subscription.get_order_subscription_by_external_id",
        return_value=subscription,
    )
    mocked_create_subscription = mocker.patch(
        "swo_aws_extension.flows.steps.create_subscription.create_subscription",
        return_value=subscription,
    )
    create_subscription = CreateSubscription()
    create_subscription(mpt_client_mock, context, next_step_mock)

    mocked_get_order_subscription.assert_called_once_with(
        mpt_client_mock, context.order["id"], "account_id"
    )
    mocked_create_subscription.assert_not_called()
    next_step_mock.assert_called_once_with(mpt_client_mock, context)
