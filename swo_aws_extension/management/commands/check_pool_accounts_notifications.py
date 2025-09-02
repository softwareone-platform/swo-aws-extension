from swo_aws_extension.aws.config import Config
from swo_aws_extension.flows.jobs.pool_notifications import check_pool_accounts_notifications
from swo_aws_extension.management.commands_helpers import StyledPrintCommand

config = Config()


class Command(StyledPrintCommand):
    """Check pool account notifications."""

    help = "Check Pool Account Notifications"

    def handle(self, *args, **options):
        """Run command."""
        self.info("Start processing Check Pool Accounts Notifications...")
        check_pool_accounts_notifications(config)
        self.success("Processing Check Pool Accounts Notifications completed.")
