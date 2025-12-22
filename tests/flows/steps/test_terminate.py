import datetime as dt

import pytest
from freezegun import freeze_time

from swo_aws_extension.flows.steps.errors import ConfigurationStepError, UnexpectedStopError
from swo_aws_extension.flows.steps.terminate import TerminateResponsibilityTransferStep


def test_pre_step_success(context_with_agreement):
    step = TerminateResponsibilityTransferStep()

    step.pre_step(context_with_agreement)  # Act

    assert context_with_agreement.transfer_id == "rt-8lr3q6sn"


def test_pre_step_missing_agreement(context_without_agreement):
    step = TerminateResponsibilityTransferStep()

    with pytest.raises(ConfigurationStepError) as exc_info:
        step.pre_step(context_without_agreement)

    assert "Agreement is required to assign transfer_id in context" in str(exc_info.value)


def test_pre_step_missing_transfer_id(context_without_transfer_id):
    step = TerminateResponsibilityTransferStep()

    with pytest.raises(ConfigurationStepError) as exc_info:
        step.pre_step(context_without_transfer_id)

    assert "Transfer ID not found in the Agreement" in str(exc_info.value)


@freeze_time("2025-06-15")
def test_process_success_current_month(context_with_agreement, mpt_client):
    context_with_agreement.transfer_id = "rt-8lr3q6sn"
    step = TerminateResponsibilityTransferStep()

    step.process(mpt_client, context_with_agreement)  # Act

    context_with_agreement.aws_client.terminate_responsibility_transfer.assert_called_once_with(
        "rt-8lr3q6sn",
        end_timestamp=(dt.datetime(2025, 7, 1, 0, 0, 0, tzinfo=dt.UTC)),  # noqa: WPS432
    )


@freeze_time("2025-12-15")
def test_process_success_december(context_with_agreement, mpt_client):
    context_with_agreement.transfer_id = "rt-8lr3q6sn"
    step = TerminateResponsibilityTransferStep()

    step.process(mpt_client, context_with_agreement)  # Act

    context_with_agreement.aws_client.terminate_responsibility_transfer.assert_called_once_with(
        "rt-8lr3q6sn",
        end_timestamp=(dt.datetime(2026, 1, 1, 0, 0, 0, tzinfo=dt.UTC)),  # noqa: WPS432
    )


@freeze_time("2025-06-15")
def test_process_exception_handling(context_with_agreement, mpt_client):
    context_with_agreement.aws_client.terminate_responsibility_transfer.side_effect = Exception(
        "AWS API error"
    )
    context_with_agreement.transfer_id = "rt-8lr3q6sn"
    step = TerminateResponsibilityTransferStep()

    with pytest.raises(UnexpectedStopError) as exc_info:  # Act
        step.process(mpt_client, context_with_agreement)

    assert "Terminate responsibility transfer" in exc_info.value.title
    assert "unhandled exception while terminating responsibility transfer" in exc_info.value.message


@freeze_time("2025-06-15")
def test_post_step_logs_success(context_with_agreement, mpt_client, caplog):
    step = TerminateResponsibilityTransferStep()

    step.post_step(mpt_client, context_with_agreement)  # Act

    assert "responsibility transfer completed successfully" in caplog.messages[0]


@freeze_time("2025-06-15")
def test_full_step_execution(mpt_client, mock_step, context_with_agreement):
    step = TerminateResponsibilityTransferStep()

    step(mpt_client, context_with_agreement, mock_step)  # Act

    context_with_agreement.aws_client.terminate_responsibility_transfer.assert_called_once()
    mock_step.assert_called_once_with(mpt_client, context_with_agreement)


@freeze_time("2025-06-15")
def test_step_stops_on_config_error(
    mocker, mpt_client, context_without_agreement, mock_teams_notification_manager, mock_step
):
    step = TerminateResponsibilityTransferStep()

    step(mpt_client, context_without_agreement, mock_step)  # Act

    mock_step.assert_not_called()
    assert mock_teams_notification_manager.mock_calls == [
        mocker.call(),
        mocker.call().notify_one_time_error(
            "Terminate responsibility transfer",
            "Agreement is required to assign transfer_id in context",
        ),
    ]


@freeze_time("2025-06-15")
def test_step_stops_on_unexpected_error(
    context_with_agreement, mock_step, mpt_client, mock_teams_notification_manager
):
    context_with_agreement.aws_client.terminate_responsibility_transfer.side_effect = Exception(
        "AWS API error"
    )
    step = TerminateResponsibilityTransferStep()

    step(mpt_client, context_with_agreement, mock_step)  # Act

    mock_step.assert_not_called()
