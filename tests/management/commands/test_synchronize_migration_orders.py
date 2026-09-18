from django.core.management import call_command

from swo_aws_extension.flows.jobs.migration_sync_processor import MigrationOrdersSyncProcessor


def test_synchronize_migration_orders(mocker):
    mock_processor = mocker.MagicMock(spec=MigrationOrdersSyncProcessor)
    mock_processor_class = mocker.patch(
        "swo_aws_extension.management.commands.synchronize_migration_orders."
        "MigrationOrdersSyncProcessor",
        return_value=mock_processor,
    )
    mock_client = mocker.patch(
        "swo_aws_extension.management.commands.synchronize_migration_orders.setup_client"
    ).return_value

    call_command("synchronize_migration_orders")  # act

    mock_processor_class.assert_called_once_with(mock_client, mocker.ANY, dry_run=False)
    mock_processor.sync.assert_called_once()


def test_synchronize_migration_orders_dry_run(mocker):
    mock_processor = mocker.MagicMock(spec=MigrationOrdersSyncProcessor)
    mock_processor_class = mocker.patch(
        "swo_aws_extension.management.commands.synchronize_migration_orders."
        "MigrationOrdersSyncProcessor",
        return_value=mock_processor,
    )
    mock_client = mocker.patch(
        "swo_aws_extension.management.commands.synchronize_migration_orders.setup_client"
    ).return_value

    call_command("synchronize_migration_orders", dry_run=True)  # act

    mock_processor_class.assert_called_once_with(mock_client, mocker.ANY, dry_run=True)
    mock_processor.sync.assert_called_once()
