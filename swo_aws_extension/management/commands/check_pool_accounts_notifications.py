from swo_aws_extension.aws.config import Config
from swo_aws_extension.flows.jobs.pool_notifications import check_pool_accounts_notifications
from swo_aws_extension.management.commands_helpers import StyledPrintCommand

config = Config()


class Command(StyledPrintCommand):
    help = "Check Pool Account Notifications"

    def handle(self, *args, **options):
        self.info("Start processing Check Pool Accounts Notifications...")
        check_pool_accounts_notifications(config)
        self.success("Processing Check Pool Accounts Notifications completed.")
