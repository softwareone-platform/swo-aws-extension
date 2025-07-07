from django.core.management import call_command


def test_demo_command(mocker):
    mocked_handle = mocker.patch(
        "swo_aws_extension.management.commands.check_pool_accounts_notifications.Command.handle"
    )
    mocked_handle.return_value = None

    call_command("check_pool_accounts_notifications")

    mocked_handle.assert_called()
