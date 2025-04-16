from django.core.management.base import BaseCommand
from mpt_extension_sdk.core.utils import setup_client

from swo_aws_extension.aws.config import Config
from swo_aws_extension.flows.jobs.synchronize_agreements import synchronize_agreements

config = Config()


class Command(BaseCommand):
    help = "Synchronize Agreements"

    def add_arguments(self, parser):
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

    def success(self, message):
        self.stdout.write(self.style.SUCCESS(message), ending="\n")

    def info(self, message):
        self.stdout.write(message, ending="\n")

    def handle(self, *args, **options):
        self.info("Start synchronizing agreements...")
        client = setup_client()
        synchronize_agreements(client, config, options["agreements"], options["dry_run"])
        self.success("Synchronizing agreements completed.")
