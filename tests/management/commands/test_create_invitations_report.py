from django.core.management import call_command


def test_create_invitations_report(mocker, settings):
    settings.MPT_PRODUCTS_IDS = ["PRD-1111-1111", "PRD-2222-2222"]
    mock_mpt_client = mocker.MagicMock()
    mock_creator = mocker.MagicMock()
    mocked_setup_client = mocker.patch(
        "swo_aws_extension.management.commands.create_invitations_report.setup_client",
        return_value=mock_mpt_client,
    )
    mocked_creator_class = mocker.patch(
        "swo_aws_extension.management.commands.create_invitations_report.InvitationsReportCreator",
        return_value=mock_creator,
    )

    call_command("create_invitations_report")  # act

    mocked_setup_client.assert_called_once()
    mocked_creator_class.assert_called_once_with(
        mock_mpt_client,
        settings.MPT_PRODUCTS_IDS,
    )
    mock_creator.create_and_notify_teams.assert_called_once()
