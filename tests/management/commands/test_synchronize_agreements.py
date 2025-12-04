import pytest
from django.core.management import call_command


@pytest.mark.parametrize("dry_run", [True, False])
def test_check_pool_notifications_agreements_ids(mocker, dry_run):
    mocked_handle = mocker.patch(
        "swo_aws_extension.management.commands.synchronize_agreements.synchronize_agreements"
    )
    mocked_handle.return_value = None

    call_command(
        "synchronize_agreements",
        agreements=["AGR-0001", "AGR-0002"],
        dry_run=dry_run,
    )  # act

    mocked_handle.assert_called_once()


@pytest.mark.parametrize("dry_run", [True, False])
def test_check_pool_notifications_all_agreements(mocker, dry_run):
    mocked_handle = mocker.patch(
        "swo_aws_extension.management.commands.synchronize_agreements.synchronize_agreements"
    )
    mocked_handle.return_value = None

    call_command(
        "synchronize_agreements",
        dry_run=dry_run,
    )  # act

    mocked_handle.assert_called_once()
