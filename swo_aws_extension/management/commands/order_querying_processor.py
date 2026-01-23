from mpt_extension_sdk.core.utils import setup_client

from swo_aws_extension.aws.config import Config
from swo_aws_extension.flows.jobs.query_order_processor import process_query_orders
from swo_aws_extension.management.commands_helpers import StyledPrintCommand

config = Config()


class Command(StyledPrintCommand):
    """Check AWS invitation state."""

    help = "Check AWS invitation states"
    name = "order_process_aws_invitations"

    def handle(self, *args, **options):  # noqa: WPS110
        """Run command."""
        self.info(f"Start processing {self.name}")
        mpt_client = setup_client()
        process_query_orders(mpt_client, config)
        self.success(f"Processing {self.name} completed.")
