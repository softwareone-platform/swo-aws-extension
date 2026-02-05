import datetime as dt

import pytest
from freezegun import freeze_time

from swo_aws_extension.aws.errors import AWSError, InvalidDateInTerminateResponsibilityError
from swo_aws_extension.constants import (
    ChannelHandshakeStatusEnum,
    ResponsibilityTransferStatus,
)
from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.steps.errors import FailStepError, SkipStepError, UnexpectedStopError
from swo_aws_extension.flows.steps.terminate import TerminateResponsibilityTransferStep

JUNE_YEAR = 2025
DECEMBER_YEAR = 2026


def _get_end_of_month(year, month):
    first_day = dt.datetime(year, month, 1, 0, 0, 0, tzinfo=dt.UTC)
    return first_day - dt.timedelta(milliseconds=1)


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
def test_process_terminates_when_end_date_past(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    mpt_client,
    aws_client_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
            billing_group_arn="arn:aws:billingconductor::123:billinggroup/test-group",
            channel_handshake_id="hs-123456",
            relationship_id="rel-123456",
        )
    )
    context = InitialAWSContext.from_order_data(order)
    context.aws_client = mock_aws_client
    _, mock_apn_client = aws_client_factory(config, "pma-id", "role-name")
    context.aws_apn_client = mock_apn_client
    mock_aws_client.get_responsibility_transfer_details.return_value = {
        "ResponsibilityTransfer": {"Status": ResponsibilityTransferStatus.ACCEPTED}
    }
    mock_apn_client.get_channel_handshake_by_id.return_value = {
        "id": "hs-123456",
        "status": ChannelHandshakeStatusEnum.ACCEPTED.value,
        "detail": {
            "startServicePeriodHandshakeDetail": {
                "endDate": dt.datetime.fromisoformat("2025-06-01T00:00:00+00:00"),
            }
        },
    }
    step = TerminateResponsibilityTransferStep(config)

    step.process(mpt_client, context)  # act

    expected_end = _get_end_of_month(JUNE_YEAR, 7)
    mock_aws_client.terminate_responsibility_transfer.assert_called_once_with(
        "rt-8lr3q6sn",
        end_timestamp=expected_end,
    )
    mock_aws_client.delete_billing_group.assert_called_once_with(
        "arn:aws:billingconductor::123:billinggroup/test-group"
    )


@freeze_time("2025-12-15")
def test_process_success_december(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    mpt_client,
    aws_client_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
            billing_group_arn="arn:aws:billingconductor::123:billinggroup/test-group",
            channel_handshake_id="hs-123456",
            relationship_id="rel-123456",
        )
    )
    context = InitialAWSContext.from_order_data(order)
    context.aws_client = mock_aws_client
    _, mock_apn_client = aws_client_factory(config, "pma-id", "role-name")
    context.aws_apn_client = mock_apn_client
    mock_aws_client.get_responsibility_transfer_details.return_value = {
        "ResponsibilityTransfer": {"Status": ResponsibilityTransferStatus.ACCEPTED}
    }
    mock_apn_client.get_channel_handshake_by_id.return_value = {
        "id": "hs-123456",
        "status": ChannelHandshakeStatusEnum.ACCEPTED.value,
        "detail": {
            "startServicePeriodHandshakeDetail": {
                "endDate": dt.datetime.fromisoformat("2025-12-01T00:00:00+00:00"),
            }
        },
    }
    step = TerminateResponsibilityTransferStep(config)

    step.process(mpt_client, context)  # act

    expected_end = _get_end_of_month(DECEMBER_YEAR, 1)
    mock_aws_client.terminate_responsibility_transfer.assert_called_once_with(
        "rt-8lr3q6sn",
        end_timestamp=expected_end,
    )
    mock_aws_client.delete_billing_group.assert_called_once_with(
        "arn:aws:billingconductor::123:billinggroup/test-group"
    )


@freeze_time("2025-06-15")
def test_process_skips_non_accepted_transfer(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    agreement_factory,
    mpt_client,
    caplog,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
        )
    )
    agreement = agreement_factory()
    context = InitialAWSContext(aws_client=mock_aws_client, order=order, agreement=agreement)
    mock_aws_client.get_responsibility_transfer_details.return_value = {
        "ResponsibilityTransfer": {"Status": "Pending"}
    }
    step = TerminateResponsibilityTransferStep(config)

    step.process(mpt_client, context)  # act

    mock_aws_client.terminate_responsibility_transfer.assert_not_called()
    mock_aws_client.delete_billing_group.assert_not_called()
    assert "Skipping termination as transfer status is Pending" in caplog.text


@freeze_time("2025-06-15")
def test_process_delete_billing_group_error(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    mpt_client,
    caplog,
    aws_client_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
            billing_group_arn="arn:aws:billingconductor::123:billinggroup/test-group",
            channel_handshake_id="hs-123456",
            relationship_id="rel-123456",
        )
    )
    context = InitialAWSContext.from_order_data(order)
    context.aws_client = mock_aws_client
    _, mock_apn_client = aws_client_factory(config, "pma-id", "role-name")
    context.aws_apn_client = mock_apn_client
    mock_aws_client.get_responsibility_transfer_details.return_value = {
        "ResponsibilityTransfer": {"Status": ResponsibilityTransferStatus.ACCEPTED}
    }
    mock_apn_client.get_channel_handshake_by_id.return_value = {
        "id": "hs-123456",
        "status": ChannelHandshakeStatusEnum.ACCEPTED.value,
        "detail": {
            "startServicePeriodHandshakeDetail": {
                "endDate": dt.datetime.fromisoformat("2025-06-01T00:00:00+00:00"),
            }
        },
    }
    mock_aws_client.delete_billing_group.side_effect = AWSError("Billing group deletion failed")
    step = TerminateResponsibilityTransferStep(config)

    step.process(mpt_client, context)  # act

    mock_aws_client.terminate_responsibility_transfer.assert_called_once()
    mock_aws_client.delete_billing_group.assert_called_once_with(
        "arn:aws:billingconductor::123:billinggroup/test-group"
    )
    assert "Failed to delete billing group with error" in caplog.text


@freeze_time("2025-06-15")
def test_process_exception_handling(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    mpt_client,
    aws_client_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
            channel_handshake_id="hs-123456",
            relationship_id="rel-123456",
        )
    )
    context = InitialAWSContext.from_order_data(order)
    context.aws_client = mock_aws_client
    _, mock_apn_client = aws_client_factory(config, "pma-id", "role-name")
    context.aws_apn_client = mock_apn_client
    mock_aws_client.get_responsibility_transfer_details.return_value = {
        "ResponsibilityTransfer": {"Status": ResponsibilityTransferStatus.ACCEPTED}
    }
    mock_apn_client.get_channel_handshake_by_id.return_value = {
        "id": "hs-123456",
        "status": ChannelHandshakeStatusEnum.ACCEPTED.value,
        "detail": {
            "startServicePeriodHandshakeDetail": {
                "endDate": dt.datetime.fromisoformat("2025-06-01T00:00:00+00:00"),
            }
        },
    }
    mock_aws_client.terminate_responsibility_transfer.side_effect = AWSError("AWS API error")
    step = TerminateResponsibilityTransferStep(config)

    with pytest.raises(UnexpectedStopError) as exc_info:
        step.process(mpt_client, context)

    assert "Terminate responsibility transfer" in exc_info.value.title


@freeze_time("2025-06-15")
def test_process_wrong_date(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    mpt_client,
    aws_client_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
            channel_handshake_id="hs-123456",
            relationship_id="rel-123456",
        )
    )
    context = InitialAWSContext.from_order_data(order)
    context.aws_client = mock_aws_client
    _, mock_apn_client = aws_client_factory(config, "pma-id", "role-name")
    context.aws_apn_client = mock_apn_client
    mock_aws_client.get_responsibility_transfer_details.return_value = {
        "ResponsibilityTransfer": {"Status": ResponsibilityTransferStatus.ACCEPTED}
    }
    mock_apn_client.get_channel_handshake_by_id.return_value = {
        "id": "hs-123456",
        "status": ChannelHandshakeStatusEnum.ACCEPTED.value,
        "detail": {
            "startServicePeriodHandshakeDetail": {
                "endDate": dt.datetime.fromisoformat("2025-06-01T00:00:00+00:00"),
            }
        },
    }
    mock_aws_client.terminate_responsibility_transfer.side_effect = (
        InvalidDateInTerminateResponsibilityError(
            "Invalid date provided for termination",
            dt.datetime.now(tz=dt.UTC),
        )
    )
    step = TerminateResponsibilityTransferStep(config)

    with pytest.raises(FailStepError):
        step.process(mpt_client, context)  # act


@freeze_time("2025-06-15")
def test_post_step_logs_success(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    agreement_factory,
    mpt_client,
    caplog,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
        )
    )
    agreement = agreement_factory()
    context = InitialAWSContext(aws_client=mock_aws_client, order=order, agreement=agreement)
    step = TerminateResponsibilityTransferStep(config)

    step.post_step(mpt_client, context)  # act

    assert "responsibility transfer termination step completed" in caplog.text


@freeze_time("2025-06-15")
def test_process_fails_when_future_date_accepted(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    mpt_client,
    aws_client_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
            channel_handshake_id="hs-123456",
            relationship_id="rel-123456",
        )
    )
    context = InitialAWSContext.from_order_data(order)
    context.aws_client = mock_aws_client
    _, mock_apn_client = aws_client_factory(config, "pma-id", "role-name")
    context.aws_apn_client = mock_apn_client
    mock_aws_client.get_responsibility_transfer_details.return_value = {
        "ResponsibilityTransfer": {"Status": ResponsibilityTransferStatus.ACCEPTED}
    }
    mock_apn_client.get_channel_handshake_by_id.return_value = {
        "id": "hs-123456",
        "status": ChannelHandshakeStatusEnum.ACCEPTED.value,
        "detail": {
            "startServicePeriodHandshakeDetail": {
                "endDate": dt.datetime.fromisoformat("2025-07-01T00:00:00+00:00"),
            }
        },
    }
    step = TerminateResponsibilityTransferStep(config)

    with pytest.raises(FailStepError) as exc_info:
        step.process(mpt_client, context)  # act

    assert exc_info.value.id == "INVALID_END_DATE"
    mock_aws_client.terminate_responsibility_transfer.assert_not_called()


@freeze_time("2025-06-15")
def test_process_warns_future_date_pending(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    mpt_client,
    aws_client_factory,
    caplog,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
            channel_handshake_id="hs-123456",
            relationship_id="rel-123456",
        )
    )
    context = InitialAWSContext.from_order_data(order)
    context.aws_client = mock_aws_client
    _, mock_apn_client = aws_client_factory(config, "pma-id", "role-name")
    context.aws_apn_client = mock_apn_client
    mock_aws_client.get_responsibility_transfer_details.return_value = {
        "ResponsibilityTransfer": {"Status": ResponsibilityTransferStatus.ACCEPTED}
    }
    mock_apn_client.get_channel_handshake_by_id.return_value = {
        "id": "hs-123456",
        "status": ChannelHandshakeStatusEnum.PENDING.value,
        "detail": {
            "startServicePeriodHandshakeDetail": {
                "endDate": dt.datetime.fromisoformat("2025-07-01T00:00:00+00:00"),
            }
        },
    }
    step = TerminateResponsibilityTransferStep(config)

    step.process(mpt_client, context)  # act

    assert "Warning - Channel handshake is in status PENDING" in caplog.text
    mock_aws_client.terminate_responsibility_transfer.assert_not_called()


@freeze_time("2025-06-15")
def test_process_fails_handshake_not_found(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    mpt_client,
    aws_client_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
            channel_handshake_id="hs-123456",
            relationship_id="rel-123456",
        )
    )
    context = InitialAWSContext.from_order_data(order)
    context.aws_client = mock_aws_client
    _, mock_apn_client = aws_client_factory(config, "pma-id", "role-name")
    context.aws_apn_client = mock_apn_client
    mock_aws_client.get_responsibility_transfer_details.return_value = {
        "ResponsibilityTransfer": {"Status": ResponsibilityTransferStatus.ACCEPTED}
    }
    mock_apn_client.get_channel_handshake_by_id.return_value = None
    step = TerminateResponsibilityTransferStep(config)

    with pytest.raises(UnexpectedStopError) as exc_info:
        step.process(mpt_client, context)  # act

    assert "Channel handshake not found" in exc_info.value.title


@freeze_time("2025-06-15")
def test_process_skips_removal_when_no_id(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    mpt_client,
    aws_client_factory,
    caplog,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
            billing_group_arn="arn:aws:billingconductor::123:billinggroup/test-group",
            channel_handshake_id="hs-123456",
            relationship_id="",
        )
    )
    context = InitialAWSContext.from_order_data(order)
    context.aws_client = mock_aws_client
    _, mock_apn_client = aws_client_factory(config, "pma-id", "role-name")
    context.aws_apn_client = mock_apn_client
    mock_aws_client.get_responsibility_transfer_details.return_value = {
        "ResponsibilityTransfer": {"Status": ResponsibilityTransferStatus.ACCEPTED}
    }
    mock_apn_client.get_channel_handshake_by_id.return_value = {
        "id": "hs-123456",
        "status": ChannelHandshakeStatusEnum.ACCEPTED.value,
        "detail": {
            "startServicePeriodHandshakeDetail": {
                "endDate": dt.datetime.fromisoformat("2025-06-01T00:00:00+00:00"),
            }
        },
    }
    step = TerminateResponsibilityTransferStep(config)

    step.process(mpt_client, context)  # act

    assert "No APN relationship ID found in the order" in caplog.text
    mock_apn_client.get_program_management_id_by_account.assert_not_called()


@freeze_time("2025-06-15")
def test_process_logs_error_when_get_pma_id_fails(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    mpt_client,
    aws_client_factory,
    caplog,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
            billing_group_arn="arn:aws:billingconductor::123:billinggroup/test-group",
            channel_handshake_id="hs-123456",
            relationship_id="rel-123456",
        )
    )
    context = InitialAWSContext.from_order_data(order)
    context.aws_client = mock_aws_client
    _, mock_apn_client = aws_client_factory(config, "pma-id", "role-name")
    context.aws_apn_client = mock_apn_client
    mock_aws_client.get_responsibility_transfer_details.return_value = {
        "ResponsibilityTransfer": {"Status": ResponsibilityTransferStatus.ACCEPTED}
    }
    mock_apn_client.get_channel_handshake_by_id.return_value = {
        "id": "hs-123456",
        "status": ChannelHandshakeStatusEnum.ACCEPTED.value,
        "detail": {
            "startServicePeriodHandshakeDetail": {
                "endDate": dt.datetime.fromisoformat("2025-06-01T00:00:00+00:00"),
            }
        },
    }
    mock_apn_client.get_program_management_id_by_account.side_effect = AWSError(
        "Failed to get PMA ID"
    )
    step = TerminateResponsibilityTransferStep(config)

    step.process(mpt_client, context)  # act

    assert "Failed to get PMA identifier with error" in caplog.text
    mock_apn_client.delete_pc_relationship.assert_not_called()


@freeze_time("2025-06-15")
def test_process_logs_error_when_delete_fails(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    mpt_client,
    aws_client_factory,
    caplog,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
            billing_group_arn="arn:aws:billingconductor::123:billinggroup/test-group",
            channel_handshake_id="hs-123456",
            relationship_id="rel-123456",
        )
    )
    context = InitialAWSContext.from_order_data(order)
    context.aws_client = mock_aws_client
    _, mock_apn_client = aws_client_factory(config, "pma-id", "role-name")
    context.aws_apn_client = mock_apn_client
    mock_aws_client.get_responsibility_transfer_details.return_value = {
        "ResponsibilityTransfer": {"Status": ResponsibilityTransferStatus.ACCEPTED}
    }
    mock_apn_client.get_channel_handshake_by_id.return_value = {
        "id": "hs-123456",
        "status": ChannelHandshakeStatusEnum.ACCEPTED.value,
        "detail": {
            "startServicePeriodHandshakeDetail": {
                "endDate": dt.datetime.fromisoformat("2025-06-01T00:00:00+00:00"),
            }
        },
    }
    mock_apn_client.get_program_management_id_by_account.return_value = "pm-123456"
    mock_apn_client.delete_pc_relationship.side_effect = AWSError("Failed to delete relationship")
    step = TerminateResponsibilityTransferStep(config)

    step.process(mpt_client, context)  # act

    assert "Failed to delete APN relationship with error" in caplog.text


@freeze_time("2025-06-15")
def test_process_logs_success_when_deleted(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    mpt_client,
    aws_client_factory,
    caplog,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
            billing_group_arn="arn:aws:billingconductor::123:billinggroup/test-group",
            channel_handshake_id="hs-123456",
            relationship_id="rel-123456",
        )
    )
    context = InitialAWSContext.from_order_data(order)
    context.aws_client = mock_aws_client
    _, mock_apn_client = aws_client_factory(config, "pma-id", "role-name")
    context.aws_apn_client = mock_apn_client
    mock_aws_client.get_responsibility_transfer_details.return_value = {
        "ResponsibilityTransfer": {"Status": ResponsibilityTransferStatus.ACCEPTED}
    }
    mock_apn_client.get_channel_handshake_by_id.return_value = {
        "id": "hs-123456",
        "status": ChannelHandshakeStatusEnum.ACCEPTED.value,
        "detail": {
            "startServicePeriodHandshakeDetail": {
                "endDate": dt.datetime.fromisoformat("2025-06-01T00:00:00+00:00"),
            }
        },
    }
    mock_apn_client.get_program_management_id_by_account.return_value = "pm-123456"
    step = TerminateResponsibilityTransferStep(config)

    step.process(mpt_client, context)  # act

    mock_apn_client.delete_pc_relationship.assert_called_once_with("pm-123456", "rel-123456")
    assert "APN relationship rel-123456 deleted" in caplog.text
