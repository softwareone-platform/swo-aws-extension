import datetime as dt

import pytest
from dateutil.relativedelta import relativedelta
from freezegun import freeze_time

from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.create_channel_handshake import CreateChannelHandshake
from swo_aws_extension.flows.steps.errors import (
    AlreadyProcessedStepError,
    SkipStepError,
    UnexpectedStopError,
)
from swo_aws_extension.parameters import get_channel_handshake_id, get_phase

FROZEN_DATE_JANUARY = "2026-01-20 10:30:00"
FROZEN_DATE_DECEMBER = "2026-12-15 10:30:00"


def _get_expected_end_date(frozen_date: str) -> dt.datetime:
    now = dt.datetime.fromisoformat(frozen_date).replace(tzinfo=dt.UTC)
    return now + relativedelta(years=1)


def test_skip_phase_is_not_expected(fulfillment_parameters_factory, order_factory, config):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CUSTOMER_ROLES.value
        )
    )
    context = PurchaseContext.from_order_data(order)

    with pytest.raises(SkipStepError):
        CreateChannelHandshake(config).pre_step(context)


def test_pre_step_already_processed(fulfillment_parameters_factory, order_factory, config):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_CHANNEL_HANDSHAKE.value,
            channel_handshake_id="hs-123456",
        )
    )
    context = PurchaseContext.from_order_data(order)

    with pytest.raises(AlreadyProcessedStepError):
        CreateChannelHandshake(config).pre_step(context)

    assert get_phase(context.order) == PhasesEnum.CHECK_CHANNEL_HANDSHAKE_STATUS.value


def test_pre_step_success(fulfillment_parameters_factory, order_factory, config):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_CHANNEL_HANDSHAKE.value,
            channel_handshake_id="",
        )
    )
    context = PurchaseContext.from_order_data(order)

    result = CreateChannelHandshake(config).pre_step(context)

    assert result is None


@freeze_time(FROZEN_DATE_JANUARY)
def test_process_success(
    order_factory,
    aws_client_factory,
    fulfillment_parameters_factory,
    config,
    mpt_client,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_CHANNEL_HANDSHAKE.value,
            relationship_id="rel-123456",
        )
    )
    context = PurchaseContext.from_order_data(order)
    context.order_authorization = {"externalIds": {"operations": "pm-account-123"}}
    _, aws_client_mock = aws_client_factory(config, "pma-id", "role-name")
    context.aws_apn_client = aws_client_mock
    aws_client_mock.get_program_management_id_by_account.return_value = "pma-identifier-123"
    aws_client_mock.create_channel_handshake.return_value = {
        "channelHandshakeDetail": {"id": "hs-new-123456"}
    }
    expected_end_date = _get_expected_end_date(FROZEN_DATE_JANUARY)

    CreateChannelHandshake(config).process(mpt_client, context)  # act

    aws_client_mock.get_program_management_id_by_account.assert_called_once_with("pm-account-123")
    aws_client_mock.create_channel_handshake.assert_called_once_with(
        pma_identifier="pma-identifier-123",
        relationship_identifier="rel-123456",
        end_date=expected_end_date,
        note="Please accept your Service Terms contract with SoftwareOne",
    )
    assert get_channel_handshake_id(context.order) == "hs-new-123456"


@freeze_time(FROZEN_DATE_DECEMBER)
def test_process_end_date_year_boundary(
    order_factory,
    aws_client_factory,
    fulfillment_parameters_factory,
    config,
    mpt_client,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_CHANNEL_HANDSHAKE.value,
            relationship_id="rel-123456",
        )
    )
    context = PurchaseContext.from_order_data(order)
    _, aws_client_mock = aws_client_factory(config, "pma-id", "role-name")
    context.aws_apn_client = aws_client_mock
    aws_client_mock.get_program_management_id_by_account.return_value = "pma-identifier-123"
    aws_client_mock.create_channel_handshake.return_value = {
        "channelHandshakeDetail": {"id": "hs-new-123456"}
    }
    expected_end_date = _get_expected_end_date(FROZEN_DATE_DECEMBER)

    CreateChannelHandshake(config).process(mpt_client, context)  # act

    aws_client_mock.create_channel_handshake.assert_called_once_with(
        pma_identifier="pma-identifier-123",
        relationship_identifier="rel-123456",
        end_date=expected_end_date,
        note="Please accept your Service Terms contract with SoftwareOne",
    )


def test_process_aws_error(
    order_factory,
    aws_client_factory,
    fulfillment_parameters_factory,
    config,
    mpt_client,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_CHANNEL_HANDSHAKE.value,
            relationship_id="rel-123456",
        )
    )
    context = PurchaseContext.from_order_data(order)
    _, aws_client_mock = aws_client_factory(config, "pma-id", "role-name")
    context.aws_apn_client = aws_client_mock
    aws_client_mock.get_program_management_id_by_account.return_value = "pma-identifier-123"
    aws_client_mock.create_channel_handshake.side_effect = AWSError("AWS API error")

    with pytest.raises(UnexpectedStopError) as error:
        CreateChannelHandshake(config).process(mpt_client, context)

    assert "Failed to create channel handshake" in str(error.value)


def test_post_step_sets_phase(
    mocker, order_factory, fulfillment_parameters_factory, mpt_client, config
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_CHANNEL_HANDSHAKE.value,
        )
    )
    context = PurchaseContext.from_order_data(order)
    step = CreateChannelHandshake(config)
    updated_order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CHANNEL_HANDSHAKE_STATUS.value
        )
    )
    mocker.patch(
        "swo_aws_extension.flows.steps.create_channel_handshake.update_order",
        return_value=updated_order,
    )

    step.post_step(mpt_client, context)  # act

    assert get_phase(context.order) == PhasesEnum.CHECK_CHANNEL_HANDSHAKE_STATUS.value
