import datetime as dt

import pytest
from freezegun import freeze_time

from swo_aws_extension.aws.errors import AWSError, InvalidDateInTerminateResponsibilityError
from swo_aws_extension.constants import (
    COMMITMENT_ENABLED_ERROR_MESSAGE,
    ChannelHandshakeStatusEnum,
    ResponsibilityTransferStatus,
    ServicePeriodTypeEnum,
)
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


def _build_handshake(
    service_period_type=ServicePeriodTypeEnum.MINIMUM_NOTICE_PERIOD,
    end_date=None,
    status=ChannelHandshakeStatusEnum.ACCEPTED.value,
):
    detail = {"servicePeriodType": service_period_type.value}
    if end_date:
        detail["endDate"] = end_date
    return {
        "id": "ch-123456",
        "status": status,
        "detail": {"startServicePeriodHandshakeDetail": detail},
    }


def _build_context(
    order_factory,
    fulfillment_parameters_factory,
    mock_aws_client,
    transfer_status=ResponsibilityTransferStatus.ACCEPTED,
    scheduled_end=None,
    relationship_end_date="",
    relationship_id="rel-123456",
    channel_handshake_id="ch-123456",
    mock_aws_apn_client=None,
    handshake=None,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            responsibility_transfer_id="rt-8lr3q6sn",
            relationship_end_date=relationship_end_date,
            relationship_id=relationship_id,
            channel_handshake_id=channel_handshake_id,
        )
    )
    context = InitialAWSContext.from_order_data(order)
    context.aws_client = mock_aws_client
    if mock_aws_apn_client is not None:
        mock_aws_apn_client.get_channel_handshake_by_id.return_value = handshake
        context.aws_apn_client = mock_aws_apn_client
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
    mock_aws_apn_client,
    mpt_client,
):
    context = _build_context(
        order_factory,
        fulfillment_parameters_factory,
        mock_aws_client,
        mock_aws_apn_client=mock_aws_apn_client,
        handshake=_build_handshake(),
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


@freeze_time("2025-06-15")
@pytest.mark.parametrize(
    "handshake_status",
    [
        ChannelHandshakeStatusEnum.ACCEPTED.value,
        ChannelHandshakeStatusEnum.PENDING.value,
    ],
)
def test_process_fails_when_commitment_is_active(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    mock_aws_apn_client,
    mpt_client,
    handshake_status,
):
    context = _build_context(
        order_factory,
        fulfillment_parameters_factory,
        mock_aws_client,
        mock_aws_apn_client=mock_aws_apn_client,
        handshake=_build_handshake(
            service_period_type=ServicePeriodTypeEnum.FIXED_COMMITMENT_PERIOD,
            end_date=_get_end_of_month(JUNE_YEAR + 1, 2),
            status=handshake_status,
        ),
    )
    step = TerminateResponsibilityTransferStep(config)

    with pytest.raises(FailStepError) as exc_info:
        step.process(mpt_client, context)

    assert str(exc_info.value) == COMMITMENT_ENABLED_ERROR_MESSAGE
    mock_aws_client.terminate_responsibility_transfer.assert_not_called()


@freeze_time("2025-06-15")
def test_process_terminates_end_of_month_when_commitment_expired(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    mock_aws_apn_client,
    mpt_client,
):
    context = _build_context(
        order_factory,
        fulfillment_parameters_factory,
        mock_aws_client,
        mock_aws_apn_client=mock_aws_apn_client,
        handshake=_build_handshake(
            service_period_type=ServicePeriodTypeEnum.FIXED_COMMITMENT_PERIOD,
            end_date=_get_end_of_month(JUNE_YEAR, 6),
        ),
    )
    step = TerminateResponsibilityTransferStep(config)

    step.process(mpt_client, context)  # act

    expected_end = _get_end_of_month(JUNE_YEAR, 7)
    mock_aws_client.terminate_responsibility_transfer.assert_called_once_with(
        "rt-8lr3q6sn",
        end_timestamp=expected_end,
    )
    assert context.termination_effective_date == expected_end
    assert get_relationship_end_date(context.order) == expected_end.isoformat()


@freeze_time("2025-06-15")
def test_process_terminates_end_of_month_when_commitment_ends_within_current_month(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    mock_aws_apn_client,
    mpt_client,
):
    context = _build_context(
        order_factory,
        fulfillment_parameters_factory,
        mock_aws_client,
        mock_aws_apn_client=mock_aws_apn_client,
        handshake=_build_handshake(
            service_period_type=ServicePeriodTypeEnum.FIXED_COMMITMENT_PERIOD,
            end_date=_get_end_of_month(JUNE_YEAR, 7) - dt.timedelta(days=5),
        ),
    )
    step = TerminateResponsibilityTransferStep(config)

    step.process(mpt_client, context)  # act

    expected_end = _get_end_of_month(JUNE_YEAR, 7)
    mock_aws_client.terminate_responsibility_transfer.assert_called_once_with(
        "rt-8lr3q6sn",
        end_timestamp=expected_end,
    )
    assert context.termination_effective_date == expected_end
    assert get_relationship_end_date(context.order) == expected_end.isoformat()


def test_process_skips_scheduling_without_channel_handshake(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    mock_aws_apn_client,
    mpt_client,
    caplog,
):
    context = _build_context(
        order_factory,
        fulfillment_parameters_factory,
        mock_aws_client,
        relationship_id="",
        channel_handshake_id="",
        mock_aws_apn_client=mock_aws_apn_client,
    )
    step = TerminateResponsibilityTransferStep(config)

    step.process(mpt_client, context)  # act

    mock_aws_apn_client.get_channel_handshake_by_id.assert_not_called()
    mock_aws_client.terminate_responsibility_transfer.assert_not_called()
    assert context.termination_effective_date is None
    assert "No channel handshake in the order" in caplog.text


def test_process_stops_when_channel_handshake_not_found(
    order_factory,
    fulfillment_parameters_factory,
    config,
    mock_aws_client,
    mock_aws_apn_client,
    mpt_client,
):
    context = _build_context(
        order_factory,
        fulfillment_parameters_factory,
        mock_aws_client,
        mock_aws_apn_client=mock_aws_apn_client,
        handshake=None,
    )
    step = TerminateResponsibilityTransferStep(config)

    with pytest.raises(UnexpectedStopError) as exc_info:
        step.process(mpt_client, context)

    assert "does not exist for relationship" in str(exc_info.value)
    mock_aws_client.terminate_responsibility_transfer.assert_not_called()


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
    mock_aws_apn_client,
    mpt_client,
):
    context = _build_context(
        order_factory,
        fulfillment_parameters_factory,
        mock_aws_client,
        mock_aws_apn_client=mock_aws_apn_client,
        handshake=_build_handshake(),
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
    mock_aws_apn_client,
    mpt_client,
):
    context = _build_context(
        order_factory,
        fulfillment_parameters_factory,
        mock_aws_client,
        mock_aws_apn_client=mock_aws_apn_client,
        handshake=_build_handshake(),
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
