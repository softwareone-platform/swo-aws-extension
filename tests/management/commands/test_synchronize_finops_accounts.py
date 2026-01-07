from django.core.management import call_command

from swo_aws_extension.flows.jobs.finops_entitlements_processor import (
    FinOpsEntitlementsProcessor,
)


def test_sync_finops_accounts(mocker):
    mock_processor = mocker.MagicMock(spec=FinOpsEntitlementsProcessor)
    mocked_handle = mocker.patch(
        "swo_aws_extension.management.commands.synchronize_finops_accounts.FinOpsEntitlementsProcessor",
        return_value=mock_processor,
    )

    call_command("synchronize_finops_accounts")  # act

    mocked_handle.assert_called_once()
    mock_processor.sync.assert_called_once()


def test_sync_finops_with_agreements(mocker):
    mock_processor = mocker.MagicMock(spec=FinOpsEntitlementsProcessor)
    mocked_handle = mocker.patch(
        "swo_aws_extension.management.commands.synchronize_finops_accounts.FinOpsEntitlementsProcessor",
        return_value=mock_processor,
    )

    call_command(
        "synchronize_finops_accounts",
        agreements=["AGR-0001", "AGR-0002"],
    )  # act

    mocked_handle.assert_called_once()
    mock_processor.sync.assert_called_once()
