from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.constants import PhasesEnum, TransferTypesEnum
from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.steps import CreateSubscription


def test_create_subscription_phase_invalid_phase(
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
    context.account_creation_status = account_creation_status_factory(account_id="account_id")
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
    context.account_creation_status = account_creation_status_factory(account_id="account_id")
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


def test_create_subscriptions_from_organization(
    mocker,
    order_factory,
    config,
    aws_client_factory,
    fulfillment_parameters_factory,
    subscription_factory,
    order_parameters_factory,
    account_creation_status_factory,
    data_aws_account_factory,
    agreement_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_SUBSCRIPTIONS
        ),
        agreement=agreement_factory(vendor_id="123456789012"),
        order_parameters=order_parameters_factory(
            account_id="",
            transfer_type=TransferTypesEnum.TRANSFER_WITH_ORGANIZATION,
        ),
    )
    subscription = subscription_factory(
        vendor_id="000000001",
        account_email="account_1@example.com",
        account_name="Account 1",
    )
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, aws_mock = aws_client_factory(config, "test_account_id", "test_role_name")
    aws_mock.list_accounts.return_value = {
        "Accounts": [
            data_aws_account_factory(
                id="000000001", name="Account 1", email="account_1@example.com"
            ),
            data_aws_account_factory(
                id="000000002", name="Account 2", email="account_2@example.com"
            ),
            data_aws_account_factory(
                id="000000003", name="Account 3", email="account_3@example.com"
            ),
        ]
    }

    context = InitialAWSContext(order=order)
    context.aws_client = aws_client
    context.account_creation_status = account_creation_status_factory(account_id="account_id")
    next_step_mock = mocker.Mock()
    mocked_get_order_subscription = mocker.patch(
        "swo_aws_extension.flows.steps.create_subscription.get_order_subscription_by_external_id",
        side_effect=[subscription, None, None],
    )
    mocked_create_subscription = mocker.patch(
        "swo_aws_extension.flows.steps.create_subscription.create_subscription",
    )
    mocked_create_subscription.side_effect = [
        subscription_factory(
            vendor_id="000000002",
            account_email="account_2@example.com",
            account_name="Account 2",
        ),
        subscription_factory(
            vendor_id="000000003",
            account_email="account_3@example.com",
            account_name="Account 3",
        ),
    ]
    create_subscription = CreateSubscription()
    create_subscription(mpt_client_mock, context, next_step_mock)

    assert mocked_get_order_subscription.call_count == 3
    assert mocked_create_subscription.call_count == 2
    next_step_mock.assert_called_once_with(mpt_client_mock, context)
