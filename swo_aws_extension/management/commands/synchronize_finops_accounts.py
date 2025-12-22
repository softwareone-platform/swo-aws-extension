from django.conf import settings
from mpt_extension_sdk.core.utils import setup_client

from swo_aws_extension.aws.config import Config
from swo_aws_extension.flows.jobs.finops_entitlements_processor import (
    FinOpsEntitlementsProcessor,
)
from swo_aws_extension.management.commands_helpers import StyledPrintCommand

config = Config()


class Command(StyledPrintCommand):
    """Command to synchronize FinOps accounts with AWS Organizations."""

    help = "Synchronize FinOps accounts with AWS Organizations."
    name = "synchronize_finops_accounts"

    def add_arguments(self, parser):
        """Add required arguments."""
        parser.add_argument(
            "--agreements",
            nargs="*",
            metavar="AGREEMENT",
            default=[],
            help="list of specific agreements to synchronize separated by space",
        )

    def handle(self, *args, **options):  # noqa: WPS110
        """Run command."""
        self.info(f"Start processing {self.name}")
        mpt_client = setup_client()
        aws_processor = FinOpsEntitlementsProcessor(
            mpt_client, config, options["agreements"], settings.MPT_PRODUCTS_IDS
        )
        aws_processor.sync()
        self.success(f"Processing {self.name} completed.")
