from django.conf import settings
from mpt_extension_sdk.core.utils import setup_client

from swo_aws_extension.management.commands_helpers import StyledPrintCommand
from swo_aws_extension.swo.mpt.sync.syncer import synchronize_agreements


class Command(StyledPrintCommand):
    """Sync agreements command."""

    help = "Synchronize Agreements"

    def add_arguments(self, parser):
        """Add required arguments."""
        parser.add_argument(
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

    def handle(self, *args, **options):  # noqa: WPS110
        """Run command."""
        self.info("Start synchronizing agreements...")
        mpt_client = setup_client()
        synchronize_agreements(
            mpt_client, options["agreements"], settings.MPT_PRODUCTS_IDS, dry_run=options["dry_run"]
        )
        self.success("Synchronizing agreements completed.")
