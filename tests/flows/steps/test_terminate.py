import datetime as dt

import pytest
from freezegun import freeze_time

from swo_aws_extension.aws.errors import AWSError, InvalidDateInTerminateResponsibilityError
from swo_aws_extension.constants import ResponsibilityTransferStatus
from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.steps.errors import (
    FailStepError,
    SkipStepError,
    UnexpectedStopError,
)
from swo_aws_extension.flows.steps.terminate import TerminateResponsibilityTransferStep
from swo_aws_extension.parameters import get_relationship_end_date

JUNE_YEAR = 2025


def _get_end_of_month(year, month):
    first_day = dt.datetime(year, month, 1, 0, 0, 0, tzinfo=dt.UTC)
    return first_day - dt.timedelta(milliseconds=1)


def _build_context(
    order_factory,
    fulfillment_parameters_factory,
    mock_aws_client,
    transfer_status=ResponsibilityTransferStatus.ACCEPTED,
    scheduled_end=None,
    relationship_end_date="",
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
            relationship_end_date=relationship_end_date,
        )
    )
    context = InitialAWSContext.from_order_data(order)
    context.aws_client = mock_aws_client
    responsibility_transfer = {"Status": transfer_status}
    if scheduled_end:
        responsibility_transfer["EndTimestamp"] = scheduled_end
    mock_aws_client.get_responsibility_transfer_details.return_value = {
        "ResponsibilityTransfer": responsibility_transfer
    }
    return context


def test_pre_step_skips_when_no_transfer_id(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="",
        )
    )
    context = InitialAWSContext(aws_client=mock_aws_client, order=order, agreement=None)
    step = TerminateResponsibilityTransferStep(config)

    with pytest.raises(SkipStepError) as exc_info:
        step.pre_step(context)

    assert "Responsibility transfer ID is missing" in str(exc_info.value)


def test_pre_step_proceeds_with_transfer_id(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    agreement_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
        )
    )
    agreement = agreement_factory()
    context = InitialAWSContext(aws_client=mock_aws_client, order=order, agreement=agreement)
    step = TerminateResponsibilityTransferStep(config)

    step.pre_step(context)  # act

    assert context.order is not None


@freeze_time("2025-06-15")
def test_process_schedules_withdrawal_with_notice_period(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    mpt_client,
):
    context = _build_context(
        order_factory,
        fulfillment_parameters_factory,
        mock_aws_client,
    )
    step = TerminateResponsibilityTransferStep(config)

    step.process(mpt_client, context)  # act

    expected_end = _get_end_of_month(JUNE_YEAR, 10)
    mock_aws_client.terminate_responsibility_transfer.assert_called_once_with(
        "rt-8lr3q6sn",
        end_timestamp=expected_end,
    )
    assert context.termination_effective_date == expected_end
    assert get_relationship_end_date(context.order) == expected_end.isoformat()


def test_process_uses_end_date_already_configured(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    mpt_client,
):
    scheduled_end = _get_end_of_month(JUNE_YEAR, 10)
    context = _build_context(
        order_factory,
        fulfillment_parameters_factory,
        mock_aws_client,
        scheduled_end=scheduled_end,
    )
    step = TerminateResponsibilityTransferStep(config)

    step.process(mpt_client, context)  # act

    mock_aws_client.terminate_responsibility_transfer.assert_not_called()
    assert context.termination_effective_date == scheduled_end
    assert get_relationship_end_date(context.order) == scheduled_end.isoformat()


def test_pre_step_already_processed_with_saved_end_date(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
):
    saved_end = _get_end_of_month(JUNE_YEAR, 10)
    context = _build_context(
        order_factory,
        fulfillment_parameters_factory,
        mock_aws_client,
        relationship_end_date=saved_end.isoformat(),
    )
    step = TerminateResponsibilityTransferStep(config)

    with pytest.raises(SkipStepError) as exc_info:
        step.pre_step(context)

    assert "end date already known" in str(exc_info.value)
    assert context.termination_effective_date == saved_end


def test_process_skips_non_accepted_transfer(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    mpt_client,
):
    context = _build_context(
        order_factory,
        fulfillment_parameters_factory,
        mock_aws_client,
        transfer_status=ResponsibilityTransferStatus.REQUESTED,
    )
    step = TerminateResponsibilityTransferStep(config)

    step.process(mpt_client, context)  # act

    mock_aws_client.terminate_responsibility_transfer.assert_not_called()
    assert context.termination_effective_date is None


@freeze_time("2025-06-15")
def test_process_fails_on_invalid_termination_date(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    mpt_client,
):
    context = _build_context(
        order_factory,
        fulfillment_parameters_factory,
        mock_aws_client,
    )
    mock_aws_client.terminate_responsibility_transfer.side_effect = (
        InvalidDateInTerminateResponsibilityError("Invalid date", _get_end_of_month(JUNE_YEAR, 9))
    )
    step = TerminateResponsibilityTransferStep(config)

    with pytest.raises(FailStepError) as exc_info:
        step.process(mpt_client, context)

    assert "invalid date in terminate responsibility agreement" in str(exc_info.value)


@freeze_time("2025-06-15")
def test_process_stops_on_aws_error(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    mpt_client,
):
    context = _build_context(
        order_factory,
        fulfillment_parameters_factory,
        mock_aws_client,
    )
    mock_aws_client.terminate_responsibility_transfer.side_effect = AWSError("AWS API error")
    step = TerminateResponsibilityTransferStep(config)

    with pytest.raises(UnexpectedStopError) as exc_info:
        step.process(mpt_client, context)

    assert "unhandled exception while terminating responsibility transfer" in str(exc_info.value)


def test_post_step_persists_parameters(
    mocker,
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    mpt_client,
    caplog,
):
    context = _build_context(
        order_factory,
        fulfillment_parameters_factory,
        mock_aws_client,
    )
    mock_update_order = mocker.patch(
        "swo_aws_extension.flows.steps.terminate.update_order",
        return_value=context.order,
    )
    step = TerminateResponsibilityTransferStep(config)

    step.post_step(mpt_client, context)  # act

    mock_update_order.assert_called_once_with(
        mpt_client, context.order_id, parameters=context.order["parameters"]
    )
    assert "responsibility transfer termination step completed" in caplog.text
