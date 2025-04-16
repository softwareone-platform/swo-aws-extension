from django.core.management.base import BaseCommand

from swo_aws_extension.aws.config import Config
from swo_aws_extension.flows.jobs.pool_notifications import check_pool_accounts_notifications

config = Config()


class Command(BaseCommand):
    help = "Check Pool Account Notifications"

    def success(self, message):
        self.stdout.write(self.style.SUCCESS(message), ending="\n")

    def info(self, message):
        self.stdout.write(message, ending="\n")

    def handle(self, *args, **options):
        self.info("Start processing Check Pool Accounts Notifications...")
        check_pool_accounts_notifications(config)
        self.success("Processing Check Pool Accounts Notifications completed.")
