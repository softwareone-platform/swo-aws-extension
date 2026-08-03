import datetime as dt

import pytest
from freezegun import freeze_time

from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.steps.errors import ScheduleStepError, SkipStepError
from swo_aws_extension.flows.steps.wait_terminate_responsibility_transfer import (
    WaitTerminateResponsibilityTransferStep,
)

END_YEAR = 2025
END_MONTH = 9


def _get_end_of_month(year, month):
    first_day = dt.datetime(year, month, 1, tzinfo=dt.UTC)
    return first_day - dt.timedelta(milliseconds=1)


END_DATE = _get_end_of_month(END_YEAR, END_MONTH)


def _build_context(order_factory, termination_effective_date=None):
    context = InitialAWSContext.from_order_data(order_factory())
    context.termination_effective_date = termination_effective_date
    return context


def test_pre_step_skips_without_end_date(order_factory, config):
    context = _build_context(order_factory)
    step = WaitTerminateResponsibilityTransferStep(config)

    with pytest.raises(SkipStepError) as exc_info:
        step.pre_step(context)

    assert "No responsibility transfer end date to wait for" in str(exc_info.value)


def test_pre_step_proceeds_with_end_date(order_factory, config):
    context = _build_context(order_factory, termination_effective_date=END_DATE)
    step = WaitTerminateResponsibilityTransferStep(config)

    step.pre_step(context)  # act

    assert context.order is not None


@freeze_time("2025-06-15")
def test_process_schedules_wait_before_end_date(order_factory, config, mpt_client):
    context = _build_context(order_factory, termination_effective_date=END_DATE)
    step = WaitTerminateResponsibilityTransferStep(config)

    with pytest.raises(ScheduleStepError) as exc_info:
        step.process(mpt_client, context)

    assert "Keeping the order in processing until that date" in str(exc_info.value)


@freeze_time("2025-06-15")
def test_call_waits_until_end_date(mocker, order_factory, config, mpt_client, caplog):
    context = _build_context(order_factory, termination_effective_date=END_DATE)
    step = WaitTerminateResponsibilityTransferStep(config)
    next_step = mocker.MagicMock()

    step(mpt_client, context, next_step)  # act

    next_step.assert_not_called()
    assert "Keeping the order in processing until that date" in caplog.text


@freeze_time("2025-09-15")
def test_call_continues_after_end_date(mocker, order_factory, config, mpt_client, caplog):
    context = _build_context(order_factory, termination_effective_date=END_DATE)
    step = WaitTerminateResponsibilityTransferStep(config)
    next_step = mocker.MagicMock()

    step(mpt_client, context, next_step)  # act

    next_step.assert_called_once_with(mpt_client, context)
    assert "end date" in caplog.text
    assert "reached" in caplog.text
    assert "responsibility transfer wait step completed" in caplog.text
