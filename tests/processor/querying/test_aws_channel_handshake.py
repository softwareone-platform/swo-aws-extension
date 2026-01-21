import datetime as dt
from typing import Any
from unittest.mock import MagicMock

import pytest
from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.constants import (
    ChannelHandshakeStatusEnum,
    OrderProcessingTemplateEnum,
    PhasesEnum,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.processors.querying.aws_channel_handshake import (
    AWSChannelHandshakeProcessor,
)


@pytest.fixture
def mock_client() -> MagicMock:
    return MagicMock(spec=MPTClient)


@pytest.fixture
def processor(mock_client: MagicMock, config: Any) -> AWSChannelHandshakeProcessor:
    return AWSChannelHandshakeProcessor(mock_client, config)


@pytest.fixture
def mock_context() -> MagicMock:
    context = MagicMock(spec=PurchaseContext)
    context.order = {}
    context.order_id = "ORD-123"
    context.aws_apn_client = MagicMock()
    return context


def test_is_querying_timeout_no_audit(
    processor: AWSChannelHandshakeProcessor, mock_context: MagicMock
) -> None:
    mock_context.order = {}

    result = processor.is_querying_timeout(mock_context)

    assert result is False


def test_is_querying_timeout_no_querying_at(
    processor: AWSChannelHandshakeProcessor, mock_context: MagicMock
) -> None:
    mock_context.order = {"audit": {}}

    result = processor.is_querying_timeout(mock_context)

    assert result is False


def test_is_querying_timeout_not_reached(
    processor: AWSChannelHandshakeProcessor, mock_context: MagicMock
) -> None:
    now = dt.datetime.now(dt.UTC)
    querying_at = (now - dt.timedelta(days=3)).isoformat()
    mock_context.order = {"audit": {"querying": {"at": querying_at}}}

    result = processor.is_querying_timeout(mock_context)

    assert result is False


def test_is_querying_timeout_reached(
    processor: AWSChannelHandshakeProcessor, mock_context: MagicMock
) -> None:
    now = dt.datetime.now(dt.UTC)
    querying_at = (now - dt.timedelta(days=5)).isoformat()
    mock_context.order = {"audit": {"querying": {"at": querying_at}}}

    result = processor.is_querying_timeout(mock_context)

    assert result is True


def test_can_process_true(processor: AWSChannelHandshakeProcessor, mock_context: MagicMock) -> None:
    mock_context.phase = PhasesEnum.CHECK_CHANNEL_HANDSHAKE_STATUS

    result = processor.can_process(mock_context)

    assert result is True


def test_can_process_false(
    processor: AWSChannelHandshakeProcessor, mock_context: MagicMock
) -> None:
    mock_context.phase = PhasesEnum.CREATE_NEW_AWS_ENVIRONMENT

    result = processor.can_process(mock_context)

    assert result is False


def test_process_handshake_not_found(
    mocker: Any,
    processor: AWSChannelHandshakeProcessor,
    mock_context: MagicMock,
) -> None:
    mocker.patch(
        "swo_aws_extension.processors.querying.aws_channel_handshake.get_relationship_id",
        return_value="rel-123",
    )
    mocker.patch(
        "swo_aws_extension.processors.querying.aws_channel_handshake.get_channel_handshake_id",
        return_value="hs-123",
    )
    mock_switch = mocker.patch(
        "swo_aws_extension.processors.querying.aws_channel_handshake.switch_order_status_to_process_and_notify"
    )
    mock_setup_aws_apn_client = mocker.patch(
        "swo_aws_extension.processors.querying.aws_channel_handshake.AWSChannelHandshakeProcessor.setup_apn_client"
    )
    mock_context.aws_apn_client.get_channel_handshakes_by_resource.return_value = []

    processor.process(mock_context)  # act

    mock_switch.assert_called_once_with(
        processor.client, mock_context, OrderProcessingTemplateEnum.EXISTING_ACCOUNT
    )
    mock_setup_aws_apn_client.assert_called_once()


def test_process_handshake_not_pending(
    mocker: Any,
    processor: AWSChannelHandshakeProcessor,
    mock_context: MagicMock,
) -> None:
    mocker.patch(
        "swo_aws_extension.processors.querying.aws_channel_handshake.get_relationship_id",
        return_value="rel-123",
    )
    mocker.patch(
        "swo_aws_extension.processors.querying.aws_channel_handshake.get_channel_handshake_id",
        return_value="hs-123",
    )
    mock_switch = mocker.patch(
        "swo_aws_extension.processors.querying.aws_channel_handshake.switch_order_status_to_process_and_notify"
    )
    mock_context.aws_apn_client.get_channel_handshakes_by_resource.return_value = [
        {"id": "hs-123", "status": ChannelHandshakeStatusEnum.ACCEPTED.value}
    ]
    mock_setup_aws_apn_client = mocker.patch(
        "swo_aws_extension.processors.querying.aws_channel_handshake.AWSChannelHandshakeProcessor.setup_apn_client"
    )

    processor.process(mock_context)  # act

    mock_switch.assert_called_once_with(
        processor.client, mock_context, OrderProcessingTemplateEnum.EXISTING_ACCOUNT
    )
    mock_setup_aws_apn_client.assert_called_once()


def test_timeout_reached(
    mocker: Any,
    processor: AWSChannelHandshakeProcessor,
    mock_context: MagicMock,
) -> None:
    mocker.patch(
        "swo_aws_extension.processors.querying.aws_channel_handshake.get_relationship_id",
        return_value="rel-123",
    )
    mocker.patch(
        "swo_aws_extension.processors.querying.aws_channel_handshake.get_channel_handshake_id",
        return_value="hs-123",
    )
    mock_switch = mocker.patch(
        "swo_aws_extension.processors.querying.aws_channel_handshake.switch_order_status_to_process_and_notify"
    )
    mock_set_phase = mocker.patch(
        "swo_aws_extension.processors.querying.aws_channel_handshake.set_phase"
    )
    mock_context.aws_apn_client.get_channel_handshakes_by_resource.return_value = [
        {"id": "hs-123", "status": ChannelHandshakeStatusEnum.PENDING.value}
    ]
    mocker.patch.object(processor, "is_querying_timeout", return_value=True)
    mock_setup_aws_apn_client = mocker.patch(
        "swo_aws_extension.processors.querying.aws_channel_handshake.AWSChannelHandshakeProcessor.setup_apn_client"
    )

    processor.process(mock_context)  # act

    mock_switch.assert_called_once_with(
        processor.client, mock_context, OrderProcessingTemplateEnum.EXISTING_ACCOUNT
    )
    mock_set_phase.assert_called_once_with({}, PhasesEnum.CHECK_CUSTOMER_ROLES)
    mock_setup_aws_apn_client.assert_called_once()


def test_timeout_not_reached(
    mocker: Any,
    processor: AWSChannelHandshakeProcessor,
    mock_context: MagicMock,
) -> None:
    mocker.patch(
        "swo_aws_extension.processors.querying.aws_channel_handshake.get_relationship_id",
        return_value="rel-123",
    )
    mocker.patch(
        "swo_aws_extension.processors.querying.aws_channel_handshake.get_channel_handshake_id",
        return_value="hs-123",
    )
    mock_switch = mocker.patch(
        "swo_aws_extension.processors.querying.aws_channel_handshake.switch_order_status_to_process_and_notify"
    )
    mock_context.aws_apn_client.get_channel_handshakes_by_resource.return_value = [
        {"id": "hs-123", "status": ChannelHandshakeStatusEnum.PENDING.value}
    ]
    mocker.patch.object(processor, "is_querying_timeout", return_value=False)
    mock_setup_aws_apn_client = mocker.patch(
        "swo_aws_extension.processors.querying.aws_channel_handshake.AWSChannelHandshakeProcessor.setup_apn_client"
    )

    processor.process(mock_context)  # act

    mock_switch.assert_not_called()
    mock_setup_aws_apn_client.assert_called_once()
