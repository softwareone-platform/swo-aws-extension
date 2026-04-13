import logging

import pytest

from swo_aws_extension.constants import DeploymentStatusEnum, PhasesEnum, SupportTypesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.check_onboard_status import CheckOnboardStatus
from swo_aws_extension.flows.steps.errors import SkipStepError, UnexpectedStopError
from swo_aws_extension.parameters import get_phase
from swo_aws_extension.swo.cloud_orchestrator.errors import CloudOrchestratorError

MODULE = "swo_aws_extension.flows.steps.check_onboard_status"
EXECUTION_ARN = "arn:aws:states:us-east-1:123456789012:execution:test"


@pytest.fixture
def purchase_context(order_factory):
    def factory(order=None):
        if order is None:
            order = order_factory()
        return PurchaseContext.from_order_data(order)

    return factory


@pytest.fixture
def onboard_status_order(order_factory, fulfillment_parameters_factory, order_parameters_factory):
    return order_factory(
        order_parameters=order_parameters_factory(),
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_ONBOARD_STATUS.value,
            execution_arn=EXECUTION_ARN,
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
    step = CheckOnboardStatus(config)

    with pytest.raises(SkipStepError):
        step.pre_step(context)


def test_pre_step_proceeds_when_phase_matches(
    order_factory, fulfillment_parameters_factory, purchase_context, config
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_ONBOARD_STATUS.value,
        )
    )
    context = purchase_context(order)
    step = CheckOnboardStatus(config)

    step.pre_step(context)  # act

    assert context.order is not None


def test_process_success(
    mocker, onboard_status_order, purchase_context, mpt_client, config, caplog
):
    context = purchase_context(onboard_status_order)
    mocker.patch(
        f"{MODULE}.check_onboard_status",
        autospec=True,
        return_value=DeploymentStatusEnum.SUCCEEDED.value,
    )
    handle_error_mock = mocker.patch(f"{MODULE}.handle_error", autospec=True)
    step = CheckOnboardStatus(config)

    with caplog.at_level(logging.INFO):
        step.process(mpt_client, context)  # act

    handle_error_mock.assert_not_called()
    assert "Onboard status check completed successfully" in caplog.text


def test_process_no_execution_arn_calls_handle_error(
    mocker,
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
    purchase_context,
    mpt_client,
    config,
):
    order = order_factory(
        order_parameters=order_parameters_factory(),
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_ONBOARD_STATUS.value,
            execution_arn="",
        ),
    )
    context = purchase_context(order)
    handle_error_mock = mocker.patch(f"{MODULE}.handle_error", autospec=True)
    step = CheckOnboardStatus(config)

    step.process(mpt_client, context)  # act

    handle_error_mock.assert_called_once()


def test_process_no_execution_arn_raises_for_pls(
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
            phase=PhasesEnum.CHECK_ONBOARD_STATUS.value,
        ),
    )
    context = purchase_context(order)
    mocker.patch(
        f"{MODULE}.handle_error", autospec=True, side_effect=UnexpectedStopError("error", "details")
    )
    step = CheckOnboardStatus(config)

    with pytest.raises(UnexpectedStopError):
        step.process(mpt_client, context)  # act


def test_process_no_execution_arn_does_not_raise_for_resold(
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
            phase=PhasesEnum.CHECK_ONBOARD_STATUS.value,
        ),
    )
    context = purchase_context(order)
    handle_error_mock = mocker.patch(f"{MODULE}.handle_error", autospec=True)
    step = CheckOnboardStatus(config)

    step.process(mpt_client, context)  # act

    handle_error_mock.assert_called_once()


def test_process_running_does_not_advance_phase(
    mocker, onboard_status_order, purchase_context, mpt_client, config, caplog
):
    context = purchase_context(onboard_status_order)
    mocker.patch(
        f"{MODULE}.check_onboard_status",
        autospec=True,
        return_value=DeploymentStatusEnum.RUNNING.value,
    )
    handle_error_mock = mocker.patch(f"{MODULE}.handle_error", autospec=True)
    update_order_mock = mocker.patch(f"{MODULE}.update_order", autospec=True)
    step = CheckOnboardStatus(config)
    with caplog.at_level(logging.INFO):
        step.process(mpt_client, context)

    step.post_step(mpt_client, context)  # act

    handle_error_mock.assert_not_called()
    update_order_mock.assert_not_called()
    assert "running" in caplog.text


def test_process_pending_does_not_advance_phase(
    mocker, onboard_status_order, purchase_context, mpt_client, config, caplog
):
    context = purchase_context(onboard_status_order)
    mocker.patch(
        f"{MODULE}.check_onboard_status",
        autospec=True,
        return_value=DeploymentStatusEnum.PENDING.value,
    )
    handle_error_mock = mocker.patch(f"{MODULE}.handle_error", autospec=True)
    update_order_mock = mocker.patch(f"{MODULE}.update_order", autospec=True)
    step = CheckOnboardStatus(config)
    with caplog.at_level(logging.INFO):
        step.process(mpt_client, context)

    step.post_step(mpt_client, context)  # act

    handle_error_mock.assert_not_called()
    update_order_mock.assert_not_called()
    assert "pending" in caplog.text


def test_process_unexpected_status_does_not_advance_phase(
    mocker, onboard_status_order, purchase_context, mpt_client, config, caplog
):
    context = purchase_context(onboard_status_order)
    mocker.patch(
        f"{MODULE}.check_onboard_status",
        autospec=True,
        return_value="unknown_status",
    )
    handle_error_mock = mocker.patch(f"{MODULE}.handle_error", autospec=True)
    update_order_mock = mocker.patch(f"{MODULE}.update_order", autospec=True)
    step = CheckOnboardStatus(config)
    step.process(mpt_client, context)

    step.post_step(mpt_client, context)  # act

    handle_error_mock.assert_not_called()
    update_order_mock.assert_not_called()
    assert "Unexpected onboard status" in caplog.text


def test_process_failed_calls_handle_error(
    mocker, onboard_status_order, purchase_context, mpt_client, config
):
    context = purchase_context(onboard_status_order)
    mocker.patch(
        f"{MODULE}.check_onboard_status",
        autospec=True,
        return_value=DeploymentStatusEnum.FAILED.value,
    )
    handle_error_mock = mocker.patch(f"{MODULE}.handle_error", autospec=True)
    step = CheckOnboardStatus(config)

    step.process(mpt_client, context)  # act

    handle_error_mock.assert_called_once()


def test_process_failed_raises_for_pls(
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
            phase=PhasesEnum.CHECK_ONBOARD_STATUS.value,
            execution_arn=EXECUTION_ARN,
        ),
    )
    context = purchase_context(order)
    mocker.patch(
        f"{MODULE}.check_onboard_status",
        autospec=True,
        return_value=DeploymentStatusEnum.FAILED.value,
    )
    mocker.patch(
        f"{MODULE}.handle_error", autospec=True, side_effect=UnexpectedStopError("error", "details")
    )
    step = CheckOnboardStatus(config)

    with pytest.raises(UnexpectedStopError):
        step.process(mpt_client, context)  # act


def test_process_failed_does_not_raise_for_resold(
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
            phase=PhasesEnum.CHECK_ONBOARD_STATUS.value,
            execution_arn=EXECUTION_ARN,
        ),
    )
    context = purchase_context(order)
    mocker.patch(
        f"{MODULE}.check_onboard_status",
        autospec=True,
        return_value=DeploymentStatusEnum.FAILED.value,
    )
    handle_error_mock = mocker.patch(f"{MODULE}.handle_error", autospec=True)
    step = CheckOnboardStatus(config)

    step.process(mpt_client, context)  # act

    handle_error_mock.assert_called_once()


def test_process_cloud_orchestrator_error_calls_handle_error(
    mocker, caplog, onboard_status_order, purchase_context, mpt_client, config
):
    context = purchase_context(onboard_status_order)
    mocker.patch(
        f"{MODULE}.check_onboard_status",
        autospec=True,
        side_effect=CloudOrchestratorError("status failed"),
    )
    handle_error_mock = mocker.patch(f"{MODULE}.handle_error", autospec=True)
    step = CheckOnboardStatus(config)

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
            phase=PhasesEnum.CHECK_ONBOARD_STATUS.value,
            execution_arn=EXECUTION_ARN,
        ),
    )
    context = purchase_context(order)
    mocker.patch(
        f"{MODULE}.check_onboard_status",
        autospec=True,
        side_effect=CloudOrchestratorError("status failed"),
    )
    mocker.patch(
        f"{MODULE}.handle_error", autospec=True, side_effect=UnexpectedStopError("error", "details")
    )
    step = CheckOnboardStatus(config)

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
            phase=PhasesEnum.CHECK_ONBOARD_STATUS.value,
            execution_arn=EXECUTION_ARN,
        ),
    )
    context = purchase_context(order)
    mocker.patch(
        f"{MODULE}.check_onboard_status",
        autospec=True,
        side_effect=CloudOrchestratorError("status failed"),
    )
    handle_error_mock = mocker.patch(f"{MODULE}.handle_error", autospec=True)
    step = CheckOnboardStatus(config)

    step.process(mpt_client, context)  # act

    handle_error_mock.assert_called_once()


def test_post_step_sets_create_subscription_phase(
    mocker,
    onboard_status_order,
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
    purchase_context,
    mpt_client,
    config,
):
    context = purchase_context(onboard_status_order)
    updated_order = order_factory(
        order_parameters=order_parameters_factory(),
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_SUBSCRIPTION.value,
        ),
    )
    update_order_mock = mocker.patch(
        f"{MODULE}.update_order", autospec=True, return_value=updated_order
    )
    step = CheckOnboardStatus(config)

    step.post_step(mpt_client, context)  # act

    assert get_phase(context.order) == PhasesEnum.CREATE_SUBSCRIPTION.value
    update_order_mock.assert_called_once()
