from typing import Any
from unittest.mock import MagicMock

import pytest
from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.constants import (
    OrderProcessingTemplateEnum,
    PhasesEnum,
    ResponsibilityTransferStatus,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.processors.querying.aws_billing_transfer_invitation import (
    AWSBillingTransferInvitationProcessor,
)


@pytest.fixture
def mock_client() -> MagicMock:
    return MagicMock(spec=MPTClient)


@pytest.fixture
def processor(mock_client: MagicMock) -> AWSBillingTransferInvitationProcessor:
    return AWSBillingTransferInvitationProcessor(mock_client)


@pytest.fixture
def mock_context() -> MagicMock:
    context = MagicMock(spec=PurchaseContext)
    context.order = {}
    context.order_id = "ORD-123"
    context.pm_account_id = "123456789012"
    context.aws_client = MagicMock()
    return context


def test_can_process_true(
    processor: AWSBillingTransferInvitationProcessor, mock_context: MagicMock
) -> None:
    mock_context.phase = PhasesEnum.CHECK_BILLING_TRANSFER_INVITATION

    result = processor.can_process(mock_context)

    assert result is True


def test_can_process_false(
    processor: AWSBillingTransferInvitationProcessor, mock_context: MagicMock
) -> None:
    mock_context.phase = PhasesEnum.CREATE_NEW_AWS_ENVIRONMENT

    result = processor.can_process(mock_context)

    assert result is False


def test_process_missing_transfer_id(
    mocker: Any,
    processor: AWSBillingTransferInvitationProcessor,
    mock_context: MagicMock,
) -> None:
    mocker.patch(
        "swo_aws_extension.processors.querying.aws_billing_transfer_invitation.get_responsibility_transfer_id",
        return_value=None,
    )

    processor.process(mock_context)  # act

    mock_context.aws_client.get_responsibility_transfer_details.assert_not_called()


def test_process_missing_pm_account_id(
    mocker: Any,
    processor: AWSBillingTransferInvitationProcessor,
    mock_context: MagicMock,
) -> None:
    mocker.patch(
        "swo_aws_extension.processors.querying.aws_billing_transfer_invitation.get_responsibility_transfer_id",
        return_value="tr-123",
    )
    mock_context.pm_account_id = None

    processor.process(mock_context)  # act

    mock_context.aws_client.get_responsibility_transfer_details.assert_not_called()


def test_process_success(
    mocker: Any,
    processor: AWSBillingTransferInvitationProcessor,
    mock_context: MagicMock,
) -> None:
    mocker.patch(
        "swo_aws_extension.processors.querying.aws_billing_transfer_invitation.get_responsibility_transfer_id",
        return_value="tr-123",
    )
    mock_config = MagicMock()
    mock_config.management_role_name = "role-name"
    mocker.patch(
        "swo_aws_extension.processors.querying.aws_billing_transfer_invitation.get_config",
        return_value=mock_config,
    )
    mock_aws_client_class = mocker.patch(
        "swo_aws_extension.processors.querying.aws_billing_transfer_invitation.AWSClient",
        return_value=mock_context.aws_client,
    )
    mock_process_invitation = mocker.patch.object(processor, "process_invitation")

    processor.process(mock_context)  # act

    mock_aws_client_class.assert_called_once_with(
        mock_config, mock_context.pm_account_id, "role-name"
    )
    mock_process_invitation.assert_called_once_with(mock_context, "tr-123")


def test_process_invitation_aws_error(
    mocker: Any,
    processor: AWSBillingTransferInvitationProcessor,
    mock_context: MagicMock,
) -> None:
    mock_context.aws_client.get_responsibility_transfer_details.side_effect = AWSError("AWS Error")
    mock_notify = mocker.patch(
        "swo_aws_extension.processors.querying.aws_billing_transfer_invitation.notify_one_time_error"
    )

    processor.process_invitation(mock_context, "tr-123")  # act

    mock_notify.assert_called_once()
    assert "Error processing AWS billing transfer invitations" in mock_notify.call_args[0]


def test_process_invitation_status_requested(
    mocker: Any,
    processor: AWSBillingTransferInvitationProcessor,
    mock_context: MagicMock,
) -> None:
    mock_context.aws_client.get_responsibility_transfer_details.return_value = {
        "ResponsibilityTransfer": {"Status": ResponsibilityTransferStatus.REQUESTED}
    }
    mock_switch = mocker.patch(
        "swo_aws_extension.processors.querying.aws_billing_transfer_invitation.switch_order_status_to_process_and_notify"
    )

    processor.process_invitation(mock_context, "tr-123")  # act

    mock_switch.assert_not_called()


def test_process_invitation_status_accepted(
    mocker: Any,
    processor: AWSBillingTransferInvitationProcessor,
    mock_context: MagicMock,
) -> None:
    mock_context.aws_client.get_responsibility_transfer_details.return_value = {
        "ResponsibilityTransfer": {"Status": ResponsibilityTransferStatus.ACCEPTED}
    }
    mock_switch = mocker.patch(
        "swo_aws_extension.processors.querying.aws_billing_transfer_invitation.switch_order_status_to_process_and_notify"
    )

    processor.process_invitation(mock_context, "tr-123")  # act

    mock_switch.assert_called_once_with(
        processor.client, mock_context, OrderProcessingTemplateEnum.NEW_ACCOUNT
    )
