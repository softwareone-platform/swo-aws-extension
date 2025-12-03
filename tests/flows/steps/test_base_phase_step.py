import pytest
from mpt_extension_sdk.flows.pipeline import Step
from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.flows.order import InitialAWSContext, PurchaseContext
from swo_aws_extension.flows.steps.base import BasePhaseStep
from swo_aws_extension.flows.steps.errors import (
    AlreadyProcessedStepError,
    ConfigurationStepError,
    QueryStepError,
    SkipStepError,
    UnexpectedStopError,
)


class DummyStep(BasePhaseStep):
    def __init__(self) -> None:
        self.pre_exc: Exception | None = None
        self.proc_exc: Exception | None = None

    def pre_step(self, context: InitialAWSContext) -> None:
        if self.pre_exc is not None:
            raise self.pre_exc

    def process(self, context: InitialAWSContext) -> None:
        if self.proc_exc is not None:
            raise self.proc_exc

    def post_step(self, context: InitialAWSContext) -> None:
        pass  # noqa: WPS420


@pytest.fixture
def initial_context(order_factory):
    order = order_factory()
    return PurchaseContext.from_order_data(order)


def _run_step(mocker, step: DummyStep, context: InitialAWSContext):
    client = mocker.MagicMock(spec=MPTClient)
    next_step = mocker.MagicMock(spec=Step)

    step(client, context, next_step)

    return client, next_step


def test_already_processed_error(mocker, initial_context, order_factory):
    step = DummyStep()
    step.pre_exc = AlreadyProcessedStepError("already processed")
    updated_order = order_factory()
    update_mock = mocker.patch(
        "swo_aws_extension.flows.steps.base.update_order",
        return_value=updated_order,
    )

    client, next_step = _run_step(mocker, step, initial_context)  # act

    next_step.assert_called_once()
    update_mock.assert_called_once_with(
        client,
        initial_context.order_id,
        parameters=initial_context.order["parameters"],
    )


def test_skip_step_error_calls_next_step(mocker, initial_context):
    step = DummyStep()
    step.pre_exc = SkipStepError("skip")

    _, next_step = _run_step(mocker, step, initial_context)  # act

    next_step.assert_called_once()


def test_configuration_error_stops_pipeline(mocker, initial_context):
    step = DummyStep()
    step.pre_exc = ConfigurationStepError("cfg")

    _, next_step = _run_step(mocker, step, initial_context)  # act

    next_step.assert_not_called()


def test_unexpected_stop_notifies_and_stops(mocker, initial_context):
    step = DummyStep()
    error = UnexpectedStopError("title", "message")
    step.proc_exc = error
    notify_mock = mocker.patch(
        "swo_aws_extension.flows.steps.base.TeamsNotificationManager.notify_one_time_error",
    )

    _, next_step = _run_step(mocker, step, initial_context)  # act

    notify_mock.assert_called_once_with(error.title, error.message)
    next_step.assert_not_called()


def test_query_step_error(mocker, initial_context):
    step = DummyStep()
    error = QueryStepError("msg", "template-id")
    step.proc_exc = error
    switch_mock = mocker.patch(
        "swo_aws_extension.flows.steps.base.switch_order_status_to_query_and_notify",
    )

    client, next_step = _run_step(mocker, step, initial_context)  # act

    switch_mock.assert_called_once_with(client, initial_context, error.template_id)
    next_step.assert_not_called()


def test_post_step_and_next_step(mocker, initial_context):
    step = DummyStep()

    _, next_step = _run_step(mocker, step, initial_context)  # act

    next_step.assert_called_once()
