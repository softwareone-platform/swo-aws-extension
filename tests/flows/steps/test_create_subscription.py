import pytest

from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.create_subscription import CreateSubscription
from swo_aws_extension.flows.steps.errors import SkipStepError
from swo_aws_extension.parameters import get_phase


@pytest.fixture
def purchase_context(order_factory):
    def factory(order=None):
        if order is None:
            order = order_factory()
        return PurchaseContext.from_order_data(order)

    return factory


@pytest.fixture
def mock_get_subscription(mocker):
    return mocker.patch(
        "swo_aws_extension.flows.steps.create_subscription.get_order_subscription_by_external_id"
    )


@pytest.fixture
def mock_create_subscription(mocker):
    return mocker.patch("swo_aws_extension.flows.steps.create_subscription.create_subscription")


def test_pre_step_skips_wrong_phase(
    order_factory, fulfillment_parameters_factory, purchase_context, config
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_NEW_AWS_ENVIRONMENT.value,
        )
    )
    context = purchase_context(order)
    step = CreateSubscription(config)

    with pytest.raises(SkipStepError):
        step.pre_step(context)


def test_pre_step_proceeds(order_factory, fulfillment_parameters_factory, purchase_context, config):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_SUBSCRIPTION.value,
        )
    )
    context = purchase_context(order)
    step = CreateSubscription(config)

    step.pre_step(context)  # act

    assert context.order is not None


def test_process_creates_subscription(
    order_factory,
    fulfillment_parameters_factory,
    purchase_context,
    mpt_client,
    mock_get_subscription,
    mock_create_subscription,
    config,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_SUBSCRIPTION.value,
        )
    )
    context = purchase_context(order)
    mock_get_subscription.return_value = None
    mock_create_subscription.return_value = {"id": "SUB-001"}
    step = CreateSubscription(config)

    step.process(mpt_client, context)  # act

    mock_create_subscription.assert_called_once()
    assert {"id": "SUB-001"} in context.subscriptions


def test_process_skips_when_subscription_exists(
    order_factory,
    fulfillment_parameters_factory,
    purchase_context,
    mpt_client,
    mock_get_subscription,
    mock_create_subscription,
    caplog,
    config,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_SUBSCRIPTION.value,
        )
    )
    context = purchase_context(order)
    mock_get_subscription.return_value = {"id": "SUB-EXISTING"}
    step = CreateSubscription(config)

    step.process(mpt_client, context)  # act

    mock_create_subscription.assert_not_called()
    assert "already exists, skipping creation" in caplog.text


def test_post_step_sets_complete_phase(
    mocker, order_factory, fulfillment_parameters_factory, mpt_client, purchase_context, config
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_SUBSCRIPTION.value,
        )
    )
    updated_order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.COMPLETED.value,
        )
    )
    context = purchase_context(order)
    mocker.patch(
        "swo_aws_extension.flows.steps.create_subscription.update_order",
        return_value=updated_order,
    )
    step = CreateSubscription(config)

    step.post_step(mpt_client, context)  # act

    assert get_phase(context.order) == PhasesEnum.COMPLETED.value


def test_post_step_calls_update_order(
    mocker, order_factory, fulfillment_parameters_factory, mpt_client, purchase_context, config
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_SUBSCRIPTION.value,
        )
    )
    updated_order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.COMPLETED.value)
    )
    context = purchase_context(order)
    mock_update = mocker.patch(
        "swo_aws_extension.flows.steps.create_subscription.update_order",
        return_value=updated_order,
    )
    step = CreateSubscription(config)

    step.post_step(mpt_client, context)  # act

    mock_update.assert_called_once_with(
        mpt_client, context.order_id, parameters=context.order["parameters"]
    )
