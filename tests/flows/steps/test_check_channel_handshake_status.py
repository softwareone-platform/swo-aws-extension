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
from swo_aws_extension.parameters import get_phase


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
