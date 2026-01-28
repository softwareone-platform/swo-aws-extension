import pytest

from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.errors import SkipStepError
from swo_aws_extension.flows.steps.onboard_services import OnboardServices
from swo_aws_extension.parameters import get_phase


@pytest.fixture
def purchase_context(order_factory):
    def factory(order=None):
        if order is None:
            order = order_factory()
        return PurchaseContext.from_order_data(order)

    return factory


def test_pre_step_skips_wrong_phase(
    order_factory, fulfillment_parameters_factory, purchase_context, config
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_NEW_AWS_ENVIRONMENT.value
        )
    )
    context = purchase_context(order)
    step = OnboardServices(config)

    with pytest.raises(SkipStepError):
        step.pre_step(context)


def test_pre_step_proceeds_when_phase_matches(
    order_factory, fulfillment_parameters_factory, purchase_context, config
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.ONBOARD_SERVICES.value,
        )
    )
    context = purchase_context(order)
    step = OnboardServices(config)

    step.pre_step(context)  # act

    assert context.order is not None


def test_process_sends_email_notification(
    mocker,
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
    mpt_client,
    purchase_context,
    config,
):
    mock_email_manager = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.flows.steps.onboard_services.EmailNotificationManager",
        return_value=mock_email_manager,
    )
    order = order_factory(
        order_parameters=order_parameters_factory(),
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.ONBOARD_SERVICES.value,
        ),
    )
    context = purchase_context(order)
    step = OnboardServices(config)

    step.process(mpt_client, context)  # act

    mock_email_manager.send_email.assert_called_once()


def test_post_step_sets_create_subscription_phase(
    mocker, order_factory, fulfillment_parameters_factory, mpt_client, purchase_context, config
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.ONBOARD_SERVICES.value,
        )
    )
    updated_order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_SUBSCRIPTION.value,
        )
    )
    context = purchase_context(order)
    mock_update = mocker.patch(
        "swo_aws_extension.flows.steps.onboard_services.update_order",
        return_value=updated_order,
    )
    step = OnboardServices(config)

    step.post_step(mpt_client, context)  # act

    assert get_phase(context.order) == PhasesEnum.CREATE_SUBSCRIPTION.value
    mock_update.assert_called_once()
    call_args = mock_update.call_args
    assert call_args[0][0] == mpt_client
    assert call_args[0][1] == context.order_id
    assert call_args[1]["parameters"] is not None
