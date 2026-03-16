import pytest

from swo_aws_extension.constants import PhasesEnum, SupportTypesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.errors import SkipStepError, UnexpectedStopError
from swo_aws_extension.flows.steps.onboard_services import OnboardServices
from swo_aws_extension.parameters import get_phase
from swo_aws_extension.swo.cloud_orchestrator.errors import CloudOrchestratorError

MODULE = "swo_aws_extension.flows.steps.onboard_services"


@pytest.fixture
def purchase_context(order_factory):
    def factory(order=None):
        if order is None:
            order = order_factory()
        return PurchaseContext.from_order_data(order)

    return factory


@pytest.fixture
def onboard_order(order_factory, fulfillment_parameters_factory, order_parameters_factory):
    return order_factory(
        order_parameters=order_parameters_factory(),
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.ONBOARD_SERVICES.value,
        ),
    )


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


def test_process_success(mocker, caplog, onboard_order, purchase_context, mpt_client, config):
    context = purchase_context(onboard_order)
    execution_arn = "arn:aws:states:us-east-1:123456789012:execution:test"
    mocker.patch(
        f"{MODULE}.get_feature_version_onboard_request",
        autospec=True,
        return_value={"payload": "data"},
    )
    mocker.patch(f"{MODULE}.onboard", autospec=True, return_value=execution_arn)
    handle_error_mock = mocker.patch(f"{MODULE}.handle_error", autospec=True)
    update_order_mock = mocker.patch(f"{MODULE}.update_order", autospec=True)
    step = OnboardServices(config)

    step.process(mpt_client, context)  # act

    handle_error_mock.assert_not_called()
    update_order_mock.assert_called_once()
    assert "Onboarding services started with execution ARN" in caplog.text
    assert execution_arn in caplog.text


def test_process_empty_execution_arn_calls_handle_error(
    mocker, onboard_order, purchase_context, mpt_client, config
):
    context = purchase_context(onboard_order)
    mocker.patch(
        f"{MODULE}.get_feature_version_onboard_request",
        autospec=True,
        return_value={"payload": "data"},
    )
    mocker.patch(f"{MODULE}.onboard", autospec=True, return_value="")
    handle_error_mock = mocker.patch(f"{MODULE}.handle_error", autospec=True)
    step = OnboardServices(config)

    step.process(mpt_client, context)  # act

    handle_error_mock.assert_called_once()


def test_process_cloud_orchestrator_error_calls_handle_error(
    mocker, caplog, onboard_order, purchase_context, mpt_client, config
):
    context = purchase_context(onboard_order)
    mocker.patch(
        f"{MODULE}.get_feature_version_onboard_request",
        autospec=True,
        return_value={"payload": "data"},
    )
    mocker.patch(
        f"{MODULE}.onboard",
        autospec=True,
        side_effect=CloudOrchestratorError("deploy failed"),
    )
    handle_error_mock = mocker.patch(f"{MODULE}.handle_error", autospec=True)
    mocker.patch(f"{MODULE}.update_order", autospec=True)
    step = OnboardServices(config)

    step.process(mpt_client, context)  # act

    handle_error_mock.assert_called_once()
    assert "CloudOrchestratorError" in caplog.text


def test_process_cloud_orchestrator_error_raises_for_pls(
    mocker,
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
    purchase_context,
    mpt_client,
    config,
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            support_type=SupportTypesEnum.PARTNER_LED_SUPPORT.value
        ),
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.ONBOARD_SERVICES.value,
        ),
    )
    context = purchase_context(order)
    mocker.patch(
        f"{MODULE}.get_feature_version_onboard_request",
        autospec=True,
        return_value={"payload": "data"},
    )
    mocker.patch(
        f"{MODULE}.onboard",
        autospec=True,
        side_effect=CloudOrchestratorError("deploy failed"),
    )
    mocker.patch(
        f"{MODULE}.handle_error",
        autospec=True,
        side_effect=UnexpectedStopError("error", "details"),
    )
    step = OnboardServices(config)

    with pytest.raises(UnexpectedStopError):
        step.process(mpt_client, context)  # act


def test_process_cloud_orchestrator_error_does_not_raise_for_resold(
    mocker,
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
    purchase_context,
    mpt_client,
    config,
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            support_type=SupportTypesEnum.AWS_RESOLD_SUPPORT.value
        ),
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.ONBOARD_SERVICES.value,
        ),
    )
    context = purchase_context(order)
    mocker.patch(
        f"{MODULE}.get_feature_version_onboard_request",
        autospec=True,
        return_value={"payload": "data"},
    )
    mocker.patch(
        f"{MODULE}.onboard",
        autospec=True,
        side_effect=CloudOrchestratorError("deploy failed"),
    )
    handle_error_mock = mocker.patch(f"{MODULE}.handle_error", autospec=True)
    step = OnboardServices(config)

    step.process(mpt_client, context)  # act

    handle_error_mock.assert_called_once()


def test_post_step_sets_check_onboard_status_phase(
    mocker,
    onboard_order,
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
    purchase_context,
    mpt_client,
    config,
):
    context = purchase_context(onboard_order)
    updated_order = order_factory(
        order_parameters=order_parameters_factory(),
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_ONBOARD_STATUS.value,
        ),
    )
    update_order_mock = mocker.patch(
        f"{MODULE}.update_order", autospec=True, return_value=updated_order
    )
    step = OnboardServices(config)

    step.post_step(mpt_client, context)  # act

    assert get_phase(context.order) == PhasesEnum.CHECK_ONBOARD_STATUS.value
    update_order_mock.assert_called_once()
