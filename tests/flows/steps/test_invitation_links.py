from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.constants import AwsHandshakeStateEnum, PhasesEnum
from swo_aws_extension.flows.steps import SendInvitationLinksStep
from swo_aws_extension.flows.steps.invitation_links import (
    AwaitInvitationLinksStep,
    map_handshakes_account_state,
)
from swo_aws_extension.parameters import get_phase


def test_map_handhsakes_account_state():
    # Mock handshakes input
    handshakes = [
        {
            "Id": "h-123",
            "State": AwsHandshakeStateEnum.REQUESTED,
            "Parties": [{"Type": "ACCOUNT", "Id": "123456789012"}],
        },
        {
            "Id": "h-456",
            "State": AwsHandshakeStateEnum.ACCEPTED,
            "Parties": [{"Type": "ACCOUNT", "Id": "987654321098"}],
        },
        {
            "Id": "h-789",
            "State": AwsHandshakeStateEnum.DECLINED,
            "Parties": [{"Type": "ACCOUNT", "Id": "567890123456"}],
        },
    ]

    # Expected output
    expected_output = {
        "123456789012": AwsHandshakeStateEnum.REQUESTED,
        "987654321098": AwsHandshakeStateEnum.ACCEPTED,
        "567890123456": AwsHandshakeStateEnum.DECLINED,
    }

    # Call the function
    result = map_handshakes_account_state(handshakes)

    # Assert the result matches the expected output
    assert result == expected_output


def test_all_accounts_are_accepted(
    mocker,
    config,
    aws_client_factory,
    order_factory,
    fulfillment_parameters_factory,
    handshake_data_factory,
):
    """
    Tests:
    - Removed accounts from orderAccountId handshakes are cancelled
    - New accounts are invited
    - Existing accounts are not invited again
    - Calls next step
    """

    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.TRANSFER_ACCOUNT,
        )
    )

    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.list_handshakes_for_organization.return_value = {
        "Handshakes": [
            handshake_data_factory("111111111111", AwsHandshakeStateEnum.ACCEPTED),
            handshake_data_factory("222222222222", AwsHandshakeStateEnum.REQUESTED),
            handshake_data_factory("444444444444", AwsHandshakeStateEnum.REQUESTED),
        ]
    }
    mock_client.invite_account_to_organization.return_value = handshake_data_factory(
        "333333333333", AwsHandshakeStateEnum.REQUESTED
    )
    mock_client.cancel_handshake.return_value = None
    next_step_mock = mocker.MagicMock()

    context = mocker.MagicMock()
    context.aws_client = aws_client
    context.get_account_ids.return_value = ["111111111111", "222222222222", "333333333333"]
    context.order_id = "test-order-id"
    context.order = order

    step_instance = SendInvitationLinksStep()
    step_instance(
        client=mocker.MagicMock(),
        context=context,
        next_step=next_step_mock,
    )

    next_step_mock.assert_called_once()
    expected_invitation = {
        "Notes": "Softwareone invite for order test-order-id.",
        "Target": {"Id": "333333333333", "Type": "ACCOUNT"},
    }
    mock_client.invite_account_to_organization.assert_called_once_with(**expected_invitation)
    mock_client.cancel_handshake.assert_called_once_with(HandshakeId="h-444444444444")


def test_error_handling_for_cancel_handshakes(
    mocker,
    config,
    aws_client_factory,
    fulfillment_parameters_factory,
    order_factory,
    handshake_data_factory,
):
    """
    Tests:
    - Handshakes to cancel: 111111111111 and 444444444444
    - Handshakes to invite: 333333333333

    Actions:
    - Handshake 111111111111 ignored as it is already Accepted
    - Handshake 444444444444 raise an error when cancelling

    Tests:
    - Invite for 333333333333 is not sent
    - Next step is not called
    """
    mock_logger = mocker.patch("swo_aws_extension.flows.steps.invitation_links.logger")
    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.list_handshakes_for_organization.return_value = {
        "Handshakes": [
            handshake_data_factory("111111111111", AwsHandshakeStateEnum.ACCEPTED),
            handshake_data_factory("222222222222", AwsHandshakeStateEnum.REQUESTED),
            handshake_data_factory("444444444444", AwsHandshakeStateEnum.REQUESTED),
        ]
    }
    mock_client.invite_account_to_organization.return_value = handshake_data_factory(
        "333333333333", AwsHandshakeStateEnum.REQUESTED
    )
    mock_client.cancel_handshake.side_effect = [AWSError("Error", "Error cancelling handshake")]
    next_step_mock = mocker.MagicMock()

    context = mocker.MagicMock()
    context.aws_client = aws_client
    context.get_account_ids.return_value = ["222222222222", "333333333333"]
    context.order_id = "test-order-id"
    context.order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.TRANSFER_ACCOUNT)
    )

    step_instance = SendInvitationLinksStep()
    step_instance(
        client=mocker.MagicMock(),
        context=context,
        next_step=next_step_mock,
    )
    mock_logger.info.assert_any_call(f"{context.order_id} - Stop - Failed to cancel invitations.")
    mock_client.cancel_handshake.assert_called_once_with(HandshakeId="h-444444444444")
    mock_client.invite_account_to_organization.assert_not_called()
    next_step_mock.assert_not_called()


def test_error_handling_for_invite_accounts(
    mocker,
    config,
    aws_client_factory,
    order_factory,
    fulfillment_parameters_factory,
    handshake_data_factory,
):
    """
    Tests:
    - Handshakes to invite: 111111111111, 222222222222

    Actions:
    - Invite 111111111111 fails
    - Invite 222222222222

    Tests:
    - Invite for 222222222222 is sent
    - Next step is not called
    """
    mock_logger = mocker.patch("swo_aws_extension.flows.steps.invitation_links.logger")
    aws_client, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_client.list_handshakes_for_organization.return_value = {"Handshakes": []}
    mock_client.invite_account_to_organization.side_effect = [
        AWSError("Error", "Error inviting account `111111111111`"),
        handshake_data_factory("333333333333", AwsHandshakeStateEnum.REQUESTED),
    ]

    next_step_mock = mocker.MagicMock()

    context = mocker.MagicMock()
    context.aws_client = aws_client
    context.get_account_ids.return_value = ["111111111111", "222222222222"]
    context.order_id = "test-order-id"
    context.order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.TRANSFER_ACCOUNT)
    )

    step_instance = SendInvitationLinksStep()
    step_instance(
        client=mocker.MagicMock(),
        context=context,
        next_step=next_step_mock,
    )

    mock_logger.info.assert_any_call(
        "test-order-id - Stop - Failed to send organization invitation links."
    )
    mock_client.invite_account_to_organization.assert_has_calls(
        [
            mocker.call(
                Target={"Id": "111111111111", "Type": "ACCOUNT"},
                Notes="Softwareone invite for order test-order-id.",
            ),
            mocker.call(
                Target={"Id": "222222222222", "Type": "ACCOUNT"},
                Notes="Softwareone invite for order test-order-id.",
            ),
        ]
    )
    next_step_mock.assert_not_called(), "Next step should not be called as there is errors"


def test_await_invitation_link_step_skipped(
    mocker, config, order_factory, fulfillment_parameters_factory, aws_client_factory
):
    aws_client, mock_aws = aws_client_factory(config, "test_account_id", "test_role_name")
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_SUBSCRIPTIONS
        ),
    )
    context = mocker.MagicMock()
    context.aws_client = aws_client
    context.order = order
    context.order_id = "test-order-id"
    next_step = mocker.MagicMock()
    step_instance = AwaitInvitationLinksStep()
    step_instance(
        client=mocker.MagicMock(),
        context=context,
        next_step=next_step,
    )
    next_step.assert_called_once()


def test_send_invitation_link_step_skipped_by_phase(
    mocker, config, order_factory, fulfillment_parameters_factory, aws_client_factory
):
    aws_client, mock_aws = aws_client_factory(config, "test_account_id", "test_role_name")
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_SUBSCRIPTIONS
        ),
    )
    context = mocker.MagicMock()
    context.aws_client = aws_client
    context.order = order
    context.order_id = "test-order-id"
    next_step = mocker.MagicMock()
    step_instance = SendInvitationLinksStep()
    step_instance(
        client=mocker.MagicMock(),
        context=context,
        next_step=next_step,
    )
    next_step.assert_called_once()


def test_await_invitation_link_step_all_accepted(
    mocker,
    config,
    order_factory,
    fulfillment_parameters_factory,
    aws_client_factory,
    handshake_data_factory,
):
    aws_client, mock_aws = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_aws.list_handshakes_for_organization.return_value = {
        "Handshakes": [
            handshake_data_factory("111111111111", AwsHandshakeStateEnum.ACCEPTED),
            handshake_data_factory("222222222222", AwsHandshakeStateEnum.ACCEPTED),
            handshake_data_factory("333333333333", AwsHandshakeStateEnum.EXPIRED),
            handshake_data_factory("444444444444", AwsHandshakeStateEnum.CANCELED),
        ]
    }
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_INVITATION_LINK
        ),
    )

    def update_order(mpt, order_id, parameters):
        order["parameters"] = parameters
        return order

    mocker.patch(
        "swo_aws_extension.flows.steps.invitation_links.update_order",
        side_effect=update_order,
    )

    context = mocker.MagicMock()
    context.aws_client = aws_client
    context.order = order
    context.order_id = "test-order-id"
    context.get_account_ids.return_value = ["111111111111", "222222222222"]
    next_step = mocker.MagicMock()
    step_instance = AwaitInvitationLinksStep()
    step_instance(
        client=mocker.MagicMock(),
        context=context,
        next_step=next_step,
    )
    assert get_phase(context.order) == PhasesEnum.CREATE_SUBSCRIPTIONS
    next_step.assert_called_once()


def test_await_invitation_link_step_await_accepted(
    mocker,
    config,
    order_factory,
    fulfillment_parameters_factory,
    aws_client_factory,
    handshake_data_factory,
):
    aws_client, mock_aws = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_aws.list_handshakes_for_organization.return_value = {
        "Handshakes": [
            handshake_data_factory("111111111111", AwsHandshakeStateEnum.ACCEPTED),
            handshake_data_factory("222222222222", AwsHandshakeStateEnum.REQUESTED),
            handshake_data_factory("333333333333", AwsHandshakeStateEnum.EXPIRED),
            handshake_data_factory("444444444444", AwsHandshakeStateEnum.CANCELED),
        ]
    }
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_INVITATION_LINK
        ),
    )

    mock_switch_order_to_query = mocker.patch(
        "swo_aws_extension.flows.steps.invitation_links.switch_order_to_query",
    )

    context = mocker.MagicMock()
    context.aws_client = aws_client
    context.order = order
    context.order_id = "test-order-id"
    context.get_account_ids.return_value = ["111111111111", "222222222222"]
    next_step = mocker.MagicMock()
    step_instance = AwaitInvitationLinksStep()
    step_instance(
        client=mocker.MagicMock(),
        context=context,
        next_step=next_step,
    )
    mock_switch_order_to_query.assert_called_once()
    assert get_phase(context.order) == PhasesEnum.CHECK_INVITATION_LINK
    next_step.assert_not_called()
