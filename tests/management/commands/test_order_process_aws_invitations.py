from django.core.management import call_command

from swo_aws_extension.flows.jobs.process_aws_invitations import AWSInvitationsProcessor


def test_order_process_aws_invitations(mocker):
    mocked_handle = mocker.patch(
        "swo_aws_extension.management.commands.order_process_aws_invitations.AWSInvitationsProcessor",
        side_effect=mocker.MagicMock(spec=AWSInvitationsProcessor),
    )
    mocked_handle.return_value = None

    call_command("order_process_aws_invitations")  # act

    mocked_handle.assert_called_once()
