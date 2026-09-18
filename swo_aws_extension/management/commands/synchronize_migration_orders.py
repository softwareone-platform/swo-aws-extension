from mpt_extension_sdk.core.utils import setup_client

from swo_aws_extension.config import Config
from swo_aws_extension.flows.jobs.migration_sync_processor import MigrationOrdersSyncProcessor
from swo_aws_extension.management.commands_helpers import StyledPrintCommand

config = Config()


class Command(StyledPrintCommand):
    """Command to synchronize the AWS migration orders with the Airtable migration table."""

    help = "Synchronize the AWS Account Migration Airtable rows with their Marketplace orders."
    name = "synchronize_migration_orders"

    def add_arguments(self, parser):
        """Add required arguments."""
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Log the Airtable changes without applying them",
        )

    def handle(self, *args, **options):  # noqa: WPS110
        """Run command."""
        self.info(f"Start processing {self.name}")
        mpt_client = setup_client()
        MigrationOrdersSyncProcessor(mpt_client, config, dry_run=options["dry_run"]).sync()
        self.success(f"Processing {self.name} completed.")
