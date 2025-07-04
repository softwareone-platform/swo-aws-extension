from datetime import datetime, timedelta

from django.core.management.base import BaseCommand

from swo_aws_extension.aws.config import Config

config = Config()


class Command(BaseCommand):
    help = "Generate Journals for monthly billing"
    name = "generate_billing_journals"

    def add_arguments(self, parser):
        # Calculate last month's date
        today = datetime.now()
        last_month = today.replace(day=1) - timedelta(days=1)
        default_year = last_month.year
        default_month = last_month.month

        parser.add_argument(
            "--year",
            type=int,
            default=default_year,
            help=f"Year for billing (4 digits, must be 2000 or higher, default: {default_year})",
        )
        parser.add_argument(
            "--month",
            type=int,
            default=default_month,
            help=f"Month for billing (1-12, default: {default_month})",
        )

    def info(self, message):
        self.stdout.write(message, ending="\n")

    def error(self, message):
        self.stderr.write(self.style.ERROR(message), ending="\n")

    def handle(self, *args, **options):
        year = options["year"]
        month = options["month"]

        if year < 2000:
            self.error(f"Year must be 2000 or higher, got {year}")
            return

        if month < 1 or month > 12:
            self.error(f"Month must be between 1 and 12, got {month}")
            return

        self.info(f"Running {self.name} for {year}-{month:02d}")
        self.info(f"Dummy command {self.name} for genereting journals")
