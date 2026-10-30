import datetime as dt

import pytest

from swo_aws_extension.constants import (
    ChannelHandshakeStatusEnum,
    OrderQueryingTemplateEnum,
    PhasesEnum,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.check_channel_handshake_status import (
    CheckChannelHandshakeStatus,
)
from swo_aws_extension.flows.steps.errors import (
    ConfigurationStepError,
    QueryStepError,
    SkipStepError,
    UnexpectedStopError,
)
from swo_aws_extension.parameters import (
    get_channel_handshake_approval_status,
    get_handshake_expiration_date,
    get_phase,
)


def test_skip_phase_is_not_expected(fulfillment_parameters_factory, order_factory, config):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_NEW_AWS_ENVIRONMENT.value
        )
    )
    context = PurchaseContext.from_order_data(order)

    with pytest.raises(SkipStepError):
        CheckChannelHandshakeStatus(config).pre_step(context)


def test_pre_step_missing_channel_handshake_id(
    fulfillment_parameters_factory, order_factory, config
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CHANNEL_HANDSHAKE_STATUS.value,
            channel_handshake_id="",
        )
    )
    context = PurchaseContext.from_order_data(order)

    with pytest.raises(ConfigurationStepError):
        CheckChannelHandshakeStatus(config).pre_step(context)


def test_pre_step_success(fulfillment_parameters_factory, order_factory, config):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CHANNEL_HANDSHAKE_STATUS.value,
            channel_handshake_id="hs-123456",
            relationship_id="rel-123456",
        )
    )
    context = PurchaseContext.from_order_data(order)

    result = CheckChannelHandshakeStatus(config).pre_step(context)

    assert result is None


def test_process_handshake_accepted(
    order_factory,
    aws_client_factory,
    fulfillment_parameters_factory,
    config,
    mpt_client,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CHANNEL_HANDSHAKE_STATUS.value,
            channel_handshake_id="hs-123456",
            relationship_id="rel-123456",
        )
    )
    context = PurchaseContext.from_order_data(order)
    _, aws_client_mock = aws_client_factory(config, "pma-id", "role-name")
    context.aws_apn_client = aws_client_mock
    aws_client_mock.get_channel_handshake_by_id.return_value = {
        "id": "hs-123456",
        "status": ChannelHandshakeStatusEnum.ACCEPTED.value,
    }

    result = CheckChannelHandshakeStatus(config).process(mpt_client, context)

    assert result is None
    aws_client_mock.get_channel_handshake_by_id.assert_called_once_with("rel-123456", "hs-123456")


def test_process_handshake_pending(
    order_factory,
    aws_client_factory,
    fulfillment_parameters_factory,
    config,
    mpt_client,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CHANNEL_HANDSHAKE_STATUS.value,
            channel_handshake_id="hs-123456",
            relationship_id="rel-123456",
        )
    )
    context = PurchaseContext.from_order_data(order)
    _, aws_client_mock = aws_client_factory(config, "pma-id", "role-name")
    context.aws_apn_client = aws_client_mock
    aws_client_mock.get_channel_handshake_by_id.return_value = {
        "id": "hs-123456",
        "status": ChannelHandshakeStatusEnum.PENDING.value,
    }

    with pytest.raises(QueryStepError) as error:
        CheckChannelHandshakeStatus(config).process(mpt_client, context)

    assert error.value.template_id == OrderQueryingTemplateEnum.HANDSHAKE_AWAITING_ACCEPTANCE.value


def test_process_handshake_not_found(
    order_factory,
    aws_client_factory,
    fulfillment_parameters_factory,
    config,
    mpt_client,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CHANNEL_HANDSHAKE_STATUS.value,
            channel_handshake_id="hs-123456",
            relationship_id="rel-123456",
        )
    )
    context = PurchaseContext.from_order_data(order)
    _, aws_client_mock = aws_client_factory(config, "pma-id", "role-name")
    context.aws_apn_client = aws_client_mock
    aws_client_mock.get_channel_handshake_by_id.return_value = None

    with pytest.raises(UnexpectedStopError):
        CheckChannelHandshakeStatus(config).process(mpt_client, context)


def test_process_handshake_other_status(
    order_factory,
    aws_client_factory,
    fulfillment_parameters_factory,
    config,
    mpt_client,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CHANNEL_HANDSHAKE_STATUS.value,
            channel_handshake_id="hs-123456",
            relationship_id="rel-123456",
        )
    )
    context = PurchaseContext.from_order_data(order)
    _, aws_client_mock = aws_client_factory(config, "pma-id", "role-name")
    context.aws_apn_client = aws_client_mock
    aws_client_mock.get_channel_handshake_by_id.return_value = {
        "id": "hs-123456",
        "status": "REJECTED",
    }

    result = CheckChannelHandshakeStatus(config).process(mpt_client, context)

    assert result is None


def test_post_step_sets_phase(
    mocker, order_factory, fulfillment_parameters_factory, mpt_client, config
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CHANNEL_HANDSHAKE_STATUS.value,
            channel_handshake_id="hs-123456",
            relationship_id="rel-123456",
        )
    )
    context = PurchaseContext.from_order_data(order)
    step = CheckChannelHandshakeStatus(config)
    updated_order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CUSTOMER_ROLES.value
        )
    )
    mocker.patch(
        "swo_aws_extension.flows.steps.check_channel_handshake_status.update_order",
        return_value=updated_order,
    )

    step.post_step(mpt_client, context)  # act

    assert get_phase(context.order) == PhasesEnum.CHECK_CUSTOMER_ROLES.value


def test_post_step_sets_custom_next_phase(
    mocker, order_factory, fulfillment_parameters_factory, mpt_client, config
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CHANNEL_HANDSHAKE_STATUS.value,
            channel_handshake_id="hs-123456",
            relationship_id="rel-123456",
        )
    )
    context = PurchaseContext.from_order_data(order)
    step = CheckChannelHandshakeStatus(config, next_phase=PhasesEnum.CREATE_SUBSCRIPTION)
    mock_update_order = mocker.patch(
        "swo_aws_extension.flows.steps.check_channel_handshake_status.update_order",
        side_effect=lambda _client, _order_id, **kwargs: {**order, **kwargs},
    )

    step.post_step(mpt_client, context)  # act

    assert get_phase(mock_update_order.call_args.kwargs) == PhasesEnum.CREATE_SUBSCRIPTION.value
    assert get_phase(context.order) == PhasesEnum.CREATE_SUBSCRIPTION.value


@pytest.mark.parametrize(
    ("period_type", "expected_expiration_date"),
    [
        ("FIXED_COMMITMENT_PERIOD", "2027-02-01"),
        ("MINIMUM_NOTICE_PERIOD", ""),
    ],
)
def test_process_accepted_handshake_sets_expiration_date(
    order_factory,
    aws_client_factory,
    fulfillment_parameters_factory,
    config,
    mpt_client,
    period_type,
    expected_expiration_date,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CHANNEL_HANDSHAKE_STATUS.value,
            channel_handshake_id="hs-123456",
            relationship_id="rel-123456",
        )
    )
    context = PurchaseContext.from_order_data(order)
    _, aws_client_mock = aws_client_factory(config, "pma-id", "role-name")
    context.aws_apn_client = aws_client_mock
    aws_client_mock.get_channel_handshake_by_id.return_value = {
        "id": "hs-123456",
        "status": ChannelHandshakeStatusEnum.ACCEPTED.value,
        "detail": {
            "startServicePeriodHandshakeDetail": {
                "servicePeriodType": period_type,
                "endDate": dt.datetime.fromisoformat("2027-02-01T00:00:00+00:00"),
            }
        },
    }

    CheckChannelHandshakeStatus(config).process(mpt_client, context)  # act

    assert get_handshake_expiration_date(context.order) == expected_expiration_date


def test_process_accepted_handshake_with_null_detail(
    order_factory,
    aws_client_factory,
    fulfillment_parameters_factory,
    config,
    mpt_client,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CHANNEL_HANDSHAKE_STATUS.value,
            channel_handshake_id="hs-123456",
            relationship_id="rel-123456",
        )
    )
    context = PurchaseContext.from_order_data(order)
    _, aws_client_mock = aws_client_factory(config, "pma-id", "role-name")
    context.aws_apn_client = aws_client_mock
    aws_client_mock.get_channel_handshake_by_id.return_value = {
        "id": "hs-123456",
        "status": ChannelHandshakeStatusEnum.ACCEPTED.value,
        "detail": None,
    }

    CheckChannelHandshakeStatus(config).process(mpt_client, context)  # act

    assert not get_handshake_expiration_date(context.order)


def test_process_accepted_handshake_keeps_saved_expiration_date(
    order_factory,
    aws_client_factory,
    fulfillment_parameters_factory,
    config,
    mpt_client,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CHANNEL_HANDSHAKE_STATUS.value,
            channel_handshake_id="hs-123456",
            relationship_id="rel-123456",
            handshake_expiration_date="2026-12-31",
        )
    )
    context = PurchaseContext.from_order_data(order)
    _, aws_client_mock = aws_client_factory(config, "pma-id", "role-name")
    context.aws_apn_client = aws_client_mock
    aws_client_mock.get_channel_handshake_by_id.return_value = {
        "id": "hs-123456",
        "status": ChannelHandshakeStatusEnum.ACCEPTED.value,
        "detail": {
            "startServicePeriodHandshakeDetail": {
                "servicePeriodType": "FIXED_COMMITMENT_PERIOD",
                "endDate": dt.datetime.fromisoformat("2027-02-01T00:00:00+00:00"),
            }
        },
    }

    CheckChannelHandshakeStatus(config).process(mpt_client, context)  # act

    assert get_handshake_expiration_date(context.order) == "2026-12-31"


@pytest.mark.parametrize("end_date", ["not-a-date", 1767225600])
def test_process_accepted_handshake_ignores_invalid_end_date(
    order_factory,
    aws_client_factory,
    fulfillment_parameters_factory,
    config,
    mpt_client,
    end_date,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CHANNEL_HANDSHAKE_STATUS.value,
            channel_handshake_id="hs-123456",
            relationship_id="rel-123456",
        )
    )
    context = PurchaseContext.from_order_data(order)
    _, aws_client_mock = aws_client_factory(config, "pma-id", "role-name")
    context.aws_apn_client = aws_client_mock
    aws_client_mock.get_channel_handshake_by_id.return_value = {
        "id": "hs-123456",
        "status": ChannelHandshakeStatusEnum.ACCEPTED.value,
        "detail": {
            "startServicePeriodHandshakeDetail": {
                "servicePeriodType": "FIXED_COMMITMENT_PERIOD",
                "endDate": end_date,
            }
        },
    }

    CheckChannelHandshakeStatus(config).process(mpt_client, context)  # act

    assert (
        get_channel_handshake_approval_status(context.order),
        get_handshake_expiration_date(context.order),
    ) == ("yes", "")


def test_process_accepted_handshake_logs_invalid_end_date_as_warning(
    caplog,
    order_factory,
    aws_client_factory,
    fulfillment_parameters_factory,
    config,
    mpt_client,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CHANNEL_HANDSHAKE_STATUS.value,
            channel_handshake_id="hs-123456",
            relationship_id="rel-123456",
        )
    )
    context = PurchaseContext.from_order_data(order)
    _, aws_client_mock = aws_client_factory(config, "pma-id", "role-name")
    context.aws_apn_client = aws_client_mock
    aws_client_mock.get_channel_handshake_by_id.return_value = {
        "id": "hs-123456",
        "status": ChannelHandshakeStatusEnum.ACCEPTED.value,
        "detail": {
            "startServicePeriodHandshakeDetail": {
                "servicePeriodType": "FIXED_COMMITMENT_PERIOD",
                "endDate": "not-a-date",
            }
        },
    }

    CheckChannelHandshakeStatus(config).process(mpt_client, context)  # act

    invalid_period_records = [
        record for record in caplog.records if "Invalid service period" in record.getMessage()
    ]
    assert [
        (record.levelname, record.exc_info is None, "not-a-date" in record.getMessage())
        for record in invalid_period_records
    ] == [("WARNING", True, True)]
