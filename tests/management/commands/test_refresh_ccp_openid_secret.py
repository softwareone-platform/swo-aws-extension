from django.core.management import call_command


def test_demo_command(mocker):
    mocked_handle = mocker.patch(
        "swo_aws_extension.management.commands.refresh_ccp_openid_secret.Command.handle"
    )
    mocked_handle.return_value = None

    call_command("refresh_ccp_openid_secret")  # act

    mocked_handle.assert_called()
