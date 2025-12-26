import datetime as dt

import pytest
from freezegun import freeze_time

from swo_aws_extension.flows.steps.errors import ConfigurationStepError, UnexpectedStopError
from swo_aws_extension.flows.steps.terminate import TerminateResponsibilityTransferStep

START_TIMESTAMP = 1767225600


class TestPreStep:
    def test_pre_step_success(self, context_with_agreement):
        """Test pre_step successfully extracts transfer_id from agreement."""
        step = TerminateResponsibilityTransferStep()

        step.pre_step(context_with_agreement)  # Act

        assert context_with_agreement.transfer_id == "rt-8lr3q6sn"

    def test_pre_step_missing_agreement(self, context_without_agreement):
        """Test pre_step raises ConfigurationStepError when agreement is missing."""
        step = TerminateResponsibilityTransferStep()

        with pytest.raises(ConfigurationStepError) as exc_info:
            step.pre_step(context_without_agreement)

        assert "Agreement is required to assign transfer_id in context" in str(exc_info.value)

    def test_pre_step_missing_transfer_id(self, context_without_transfer_id):
        """Test pre_step raises ConfigurationStepError when transfer_id not found."""
        step = TerminateResponsibilityTransferStep()

        with pytest.raises(ConfigurationStepError) as exc_info:
            step.pre_step(context_without_transfer_id)

        assert "Transfer ID not found in the Agreement" in str(exc_info.value)


@freeze_time("2025-06-15")
class TestProcessStep:
    def test_process_success_current_month(self, mocker, context_with_agreement):
        """Test process successfully terminates responsibility transfer in current month."""
        context_with_agreement.transfer_id = "rt-8lr3q6sn"
        step = TerminateResponsibilityTransferStep()

        step.process(context_with_agreement)  # Act

        context_with_agreement.aws_client.terminate_responsibility_transfer.assert_called_once_with(
            "rt-8lr3q6sn",
            end_timestamp=(dt.datetime(2025, 7, 1, 0, 0, 0, tzinfo=dt.UTC)),  # noqa: WPS432
        )

    @freeze_time("2025-12-15")
    def test_process_success_december(self, mocker, context_with_agreement):
        """Test process successfully terminates responsibility transfer in December."""
        context_with_agreement.transfer_id = "rt-8lr3q6sn"
        step = TerminateResponsibilityTransferStep()

        step.process(context_with_agreement)  # Act

        context_with_agreement.aws_client.terminate_responsibility_transfer.assert_called_once_with(
            "rt-8lr3q6sn",
            end_timestamp=(dt.datetime(2026, 1, 1, 0, 0, 0, tzinfo=dt.UTC)),  # noqa: WPS432
        )

    def test_process_exception_handling(self, mocker, context_with_agreement):
        """Test process raises UnexpectedStopError when AWS client fails."""
        context_with_agreement.aws_client.terminate_responsibility_transfer.side_effect = Exception(
            "AWS API error"
        )
        context_with_agreement.transfer_id = "rt-8lr3q6sn"
        step = TerminateResponsibilityTransferStep()

        with pytest.raises(UnexpectedStopError) as exc_info:  # Act
            step.process(context_with_agreement)

        assert "Terminate responsibility transfer" in exc_info.value.title
        assert (
            "unhandled exception while terminating responsibility transfer"
            in exc_info.value.message
        )


@freeze_time("2025-06-15")
def test_post_step_logs_success(context_with_agreement, mpt_client, caplog):
    """Test post_step logs successful completion."""
    step = TerminateResponsibilityTransferStep()

    step.post_step(mpt_client, context_with_agreement)  # Act

    assert caplog.messages == [
        "AGR-2119-4550-8674-5962 - responsibility transfer completed successfully"
    ]


@freeze_time("2025-06-15")
class TestAllSteps:
    def test_full_step_execution_with_base_step(
        self, mpt_client, mock_step, context_with_agreement
    ):
        """Test full step execution through BasePhaseStep __call__ method."""
        step = TerminateResponsibilityTransferStep()

        step(mpt_client, context_with_agreement, mock_step)  # Act

        context_with_agreement.aws_client.terminate_responsibility_transfer.assert_called_once()
        mock_step.assert_called_once_with(mpt_client, context_with_agreement)

    def test_step_stops_on_config_error(
        self,
        mocker,
        mpt_client,
        context_without_agreement,
        mock_teams_notification_manager,
        mock_step,
    ):
        """Test that step stops execution on ConfigurationStepError."""
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

    def test_step_stops_on_unexpected_error(
        self, context_with_agreement, mock_step, mpt_client, mock_teams_notification_manager
    ):
        """Test that step stops execution on UnexpectedStopError."""
        context_with_agreement.aws_client.terminate_responsibility_transfer.side_effect = Exception(
            "AWS API error"
        )
        step = TerminateResponsibilityTransferStep()

        step(mpt_client, context_with_agreement, mock_step)  # Act

        mock_step.assert_not_called()
