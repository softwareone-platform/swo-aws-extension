from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.constants import PhasesEnum, TransferTypesEnum
from swo_aws_extension.flows.order import ChangeContext, InitialAWSContext
from swo_aws_extension.flows.steps import CreateSubscription
from swo_aws_extension.flows.steps.create_subscription import (
    CreateChangeSubscriptionStep,
    SynchronizeAgreementSubscriptionsStep,
)


def test_create_subscription_phase_invalid_phase(
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

    create_subscription = CreateSubscription()
    create_subscription(mpt_client_mock, context, next_step_mock)

    next_step_mock.assert_called_once_with(mpt_client_mock, context)


def test_create_subscription_new_account(
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
            phase=PhasesEnum.CREATE_SUBSCRIPTIONS.value
        ),
    )
    subscription = subscription_factory(
        lines=[{"id": order_line["id"]} for order_line in order["lines"]]
    )
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

    context = InitialAWSContext.from_order_data(order)
    context.aws_client = aws_client
    context.account_creation_status = account_creation_status_factory(account_id="account_id")
    next_step_mock = mocker.Mock()

    create_subscription = CreateSubscription()
    create_subscription(mpt_client_mock, context, next_step_mock)

    mocked_get_order_subscription.assert_called_once_with(
        mpt_client_mock, context.order["id"], "account_id"
    )
    del subscription["id"]
    del subscription["status"]
    del subscription["agreement"]
    mocked_create_subscription.assert_called_once_with(
        mpt_client_mock, context.order_id, subscription
    )
    next_step_mock.assert_called_once_with(mpt_client_mock, context)


def test_phase_subscription_already_created(
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
            phase=PhasesEnum.CREATE_SUBSCRIPTIONS.value
        ),
        order_parameters=order_parameters_factory(account_id=""),
    )
    subscription = subscription_factory()
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")

    context = InitialAWSContext.from_order_data(order)
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


def test_synchronize_agreement_subscriptions(
    mocker,
    order_factory,
    config,
    aws_client_factory,
    fulfillment_parameters_factory,
    agreement_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_SUBSCRIPTIONS.value
        ),
    )
    mock_agreement = agreement_factory()
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")

    context = InitialAWSContext.from_order_data(order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()

    mocked_sync_agreement_subscriptions = mocker.patch(
        "swo_aws_extension.flows.steps.create_subscription.sync_agreement_subscriptions"
    )
    mocked_get_agreement = mocker.patch(
        "swo_aws_extension.flows.steps.create_subscription.get_agreement",
        return_value=mock_agreement,
    )

    create_organization_subscriptions = SynchronizeAgreementSubscriptionsStep()
    create_organization_subscriptions(mpt_client_mock, context, next_step_mock)

    mocked_sync_agreement_subscriptions.assert_called_once_with(
        mpt_client_mock, aws_client, mock_agreement
    )
    mocked_get_agreement.assert_called_once_with(mpt_client_mock, context.agreement["id"])
    next_step_mock.assert_called_once_with(mpt_client_mock, context)


def test_create_subscription_transfer_account(
    mocker,
    order_factory,
    config,
    aws_client_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
    subscription_factory,
    account_creation_status_factory,
    aws_accounts_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_SUBSCRIPTIONS.value
        ),
        order_parameters=order_parameters_factory(
            transfer_type=TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION.value
        ),
    )
    subscription = subscription_factory(
        name="Subscription for Test Account (123456789012)",
        account_name="Test Account",
        account_email="test@example.com",
        vendor_id="123456789012",
        lines=[{"id": order_line["id"]} for order_line in order["lines"]],
    )
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.list_accounts.return_value = aws_accounts_factory()
    mocked_get_order_subscription = mocker.patch(
        "swo_aws_extension.flows.steps.create_subscription.get_order_subscription_by_external_id",
        return_value=None,
    )
    mocked_create_subscription = mocker.patch(
        "swo_aws_extension.flows.steps.create_subscription.create_subscription",
        return_value=subscription,
    )

    context = InitialAWSContext.from_order_data(order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()

    create_subscription = CreateSubscription()
    create_subscription(mpt_client_mock, context, next_step_mock)

    mocked_get_order_subscription.assert_called_once_with(
        mpt_client_mock, context.order["id"], "123456789012"
    )
    del subscription["id"]
    del subscription["status"]
    del subscription["agreement"]
    mocked_create_subscription.assert_called_once_with(
        mpt_client_mock, context.order_id, subscription
    )
    next_step_mock.assert_called_once_with(mpt_client_mock, context)


def test_transfer_account_no_accounts(
    mocker,
    order_factory,
    config,
    aws_client_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
    subscription_factory,
    account_creation_status_factory,
    aws_accounts_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_SUBSCRIPTIONS.value
        ),
        order_parameters=order_parameters_factory(
            transfer_type=TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION.value
        ),
    )
    subscription = subscription_factory(
        name="Subscription for Test Account (123456789012)",
        account_name="Test Account",
        account_email="test@example.com",
        vendor_id="123456789012",
    )
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.list_accounts.return_value = aws_accounts_factory(status="SUSPENDED")
    mocked_get_order_subscription = mocker.patch(
        "swo_aws_extension.flows.steps.create_subscription.get_order_subscription_by_external_id",
        return_value=None,
    )
    mocked_create_subscription = mocker.patch(
        "swo_aws_extension.flows.steps.create_subscription.create_subscription",
        return_value=subscription,
    )

    context = InitialAWSContext.from_order_data(order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()

    create_subscription = CreateSubscription()
    create_subscription(mpt_client_mock, context, next_step_mock)

    mocked_get_order_subscription.assert_not_called()
    mocked_create_subscription.assert_not_called()
    next_step_mock.assert_not_called()


def test_create_change_subscription(
    mocker,
    order_factory,
    config,
    aws_client_factory,
    fulfillment_parameters_factory,
    subscription_factory,
    account_creation_status_factory,
    order_parameters_factory,
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            change_order_email="test@example.com", change_order_name="Test Account"
        )
    )
    subscription = subscription_factory(
        name="Subscription for Test Account (account_id)",
        account_name="Test Account",
        account_email="test@example.com",
        vendor_id="account_id",
        lines=[{"id": order_line["id"]} for order_line in order["lines"]],
    )
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")

    context = ChangeContext.from_order_data(order)
    context.aws_client = aws_client
    context.account_creation_status = account_creation_status_factory(account_id="account_id")
    next_step_mock = mocker.Mock()

    mocked_get_order_subscription = mocker.patch(
        "swo_aws_extension.flows.steps.create_subscription.get_order_subscription_by_external_id",
        return_value=None,
    )
    mocked_create_subscription = mocker.patch(
        "swo_aws_extension.flows.steps.create_subscription.create_subscription",
        return_value=subscription,
    )

    create_change_subscription = CreateChangeSubscriptionStep()
    create_change_subscription(mpt_client_mock, context, next_step_mock)

    mocked_get_order_subscription.assert_called_once_with(
        mpt_client_mock, context.order["id"], "account_id"
    )
    del subscription["id"]
    del subscription["status"]
    del subscription["agreement"]
    mocked_create_subscription.assert_called_once_with(
        mpt_client_mock, context.order_id, subscription
    )
    next_step_mock.assert_called_once_with(mpt_client_mock, context)


def test_change_subscription_already_exists(
    mocker,
    order_factory,
    config,
    aws_client_factory,
    fulfillment_parameters_factory,
    subscription_factory,
    account_creation_status_factory,
    order_parameters_factory,
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            change_order_email="test@example.com", change_order_name="Test Account"
        )
    )
    existing_subscription = subscription_factory()
    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")

    context = ChangeContext.from_order_data(order)
    context.aws_client = aws_client
    context.account_creation_status = account_creation_status_factory(account_id="account_id")
    next_step_mock = mocker.Mock()

    mocked_get_order_subscription = mocker.patch(
        "swo_aws_extension.flows.steps.create_subscription.get_order_subscription_by_external_id",
        return_value=existing_subscription,
    )
    mocked_create_subscription = mocker.patch(
        "swo_aws_extension.flows.steps.create_subscription.create_subscription"
    )

    create_change_subscription = CreateChangeSubscriptionStep()
    create_change_subscription(mpt_client_mock, context, next_step_mock)

    mocked_get_order_subscription.assert_called_once_with(
        mpt_client_mock, context.order["id"], "account_id"
    )
    mocked_create_subscription.assert_not_called()
    next_step_mock.assert_called_once_with(mpt_client_mock, context)
