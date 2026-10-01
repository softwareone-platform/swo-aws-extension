import datetime as dt
from unittest.mock import ANY

from django.core.management import call_command
from freezegun import freeze_time

from swo_aws_extension.flows.jobs.migration_sync_processor import MigrationOrdersSyncProcessor

MODULE = "swo_aws_extension.management.commands.synchronize_migration_orders"
RUN_DATE = dt.date.fromisoformat("2026-09-21")


@freeze_time("2026-09-21T03:00:00Z")
def test_synchronize_migration_orders(mocker):
    mock_processor = mocker.MagicMock(spec=MigrationOrdersSyncProcessor)
    mock_processor_class = mocker.patch(
        f"{MODULE}.MigrationOrdersSyncProcessor", return_value=mock_processor
    )
    mock_client = mocker.patch(f"{MODULE}.setup_client").return_value

    call_command("synchronize_migration_orders")  # act

    mock_processor_class.assert_called_once_with(mock_client, ANY, RUN_DATE, dry_run=False)
    mock_processor.sync.assert_called_once()


@freeze_time("2026-09-21T03:00:00Z")
def test_synchronize_migration_orders_dry_run(mocker):
    mock_processor = mocker.MagicMock(spec=MigrationOrdersSyncProcessor)
    mock_processor_class = mocker.patch(
        f"{MODULE}.MigrationOrdersSyncProcessor", return_value=mock_processor
    )
    mock_client = mocker.patch(f"{MODULE}.setup_client").return_value

    call_command("synchronize_migration_orders", dry_run=True)  # act

    mock_processor_class.assert_called_once_with(mock_client, ANY, RUN_DATE, dry_run=True)
    mock_processor.sync.assert_called_once()
