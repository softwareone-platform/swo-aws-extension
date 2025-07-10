from django.core.management import call_command


def test_check_pool_account_notifications(mocker):
    mocked_handle = mocker.patch(
        "swo_aws_extension.management.commands.check_pool_accounts_notifications.check_pool_accounts_notifications"
    )
    mocked_handle.return_value = None

    call_command("check_pool_accounts_notifications")

    mocked_handle.assert_called()
