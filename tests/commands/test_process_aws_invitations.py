from django.core.management import call_command

from swo_aws_extension.flows.jobs.process_aws_invitations import AWSInvitationsProcessor


def test_order_process_aws_invitations_command(mocker):
    mock_processor = mocker.MagicMock(spec=AWSInvitationsProcessor)
    mocker.patch(
        "swo_aws_extension.management.commands.order_process_aws_invitations.AWSInvitationsProcessor",
        return_value=mock_processor,
    )
    call_command("order_process_aws_invitations")
    mock_processor.process_aws_invitations.assert_called()
