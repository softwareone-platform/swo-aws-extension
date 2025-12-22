from django.core.management import call_command

from swo_aws_extension.flows.jobs.op_scale_entitlements_processor import (
    OpScaleEntitlementsProcessor,
)


def test_sync_op_scale_accounts(mocker):
    mocked_handle = mocker.patch(
        "swo_aws_extension.management.commands.synchronize_op_scale_accounts.OpScaleEntitlementsProcessor",
        side_effect=mocker.MagicMock(spec=OpScaleEntitlementsProcessor),
    )
    mocked_handle.return_value = None

    call_command("synchronize_op_scale_accounts")  # act

    mocked_handle.assert_called_once()


def test_sync_op_scale_with_agreements(mocker):
    mocked_handle = mocker.patch(
        "swo_aws_extension.management.commands.synchronize_op_scale_accounts.OpScaleEntitlementsProcessor",
        side_effect=mocker.MagicMock(spec=OpScaleEntitlementsProcessor),
    )
    mocked_handle.return_value = None

    call_command(
        "synchronize_op_scale_accounts",
        agreements=["AGR-0001", "AGR-0002"],
    )  # act

    mocked_handle.assert_called_once()
