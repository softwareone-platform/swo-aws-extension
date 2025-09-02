from django.conf import settings

from swo_aws_extension.aws.config import Config
from swo_aws_extension.flows.jobs.synchronize_agreements import synchronize_agreements
from swo_aws_extension.management.commands_helpers import StyledPrintCommand
from swo_aws_extension.shared import mpt_client

config = Config()


class Command(StyledPrintCommand):
    """Sync agreements command."""

    help = "Synchronize Agreements"

    def add_arguments(self, parser):
        """Add required arguments."""
        mutex_group = parser.add_mutually_exclusive_group()
        mutex_group.add_argument(
            "--agreements",
            nargs="*",
            metavar="AGREEMENT",
            default=[],
            help="list of specific agreements to synchronize separated by space",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Test synchronization without making changes",
        )

    def handle(self, *args, **options):
        """Run command."""
        self.info("Start synchronizing agreements...")
        synchronize_agreements(
            mpt_client,
            config,
            options["agreements"],
            settings.MPT_PRODUCTS_IDS,
            dry_run=options["dry_run"],
        )
        self.success("Synchronizing agreements completed.")
