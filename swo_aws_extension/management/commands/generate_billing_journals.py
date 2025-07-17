import re
from datetime import datetime

from django.conf import settings

from swo_aws_extension.aws.config import Config
from swo_aws_extension.constants import COMMAND_INVALID_BILLING_DATE
from swo_aws_extension.flows.jobs.billing_journal import (
    BillingJournalGenerator,
)
from swo_aws_extension.management.commands_helpers import StyledPrintCommand
from swo_aws_extension.shared import mpt_client

config = Config()


class Command(StyledPrintCommand):
    help = "Generate Journals for monthly billing"
    name = "generate_billing_journals"

    def add_arguments(self, parser):
        # Calculate last month's date
        today = datetime.now()
        default_year = today.year
        default_month = today.month

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
        mutex_group = parser.add_mutually_exclusive_group()
        mutex_group.add_argument(
            "--authorizations",
            nargs="*",
            metavar="AUTHORIZATION",
            default=[],
            help="list of specific authorizations to synchronize separated by space",
        )

    def info(self, message):
        self.stdout.write(message, ending="\n")

    def error(self, message):
        self.stderr.write(self.style.ERROR(message), ending="\n")

    def raise_for_invalid_date(self, year, month):
        if year < 2025:
            raise ValueError(f"Year must be 2025 or higher, got {year}")

        if month < 1 or month > 12:
            raise ValueError(f"Invalid month. Month must be between 1 and 12. Got {month} instead.")

        invoice_date = datetime(year, month, 5, 0, 0, 0, 0)
        current_date = datetime.now()
        is_valid_billing_date = current_date < invoice_date
        if is_valid_billing_date:
            raise ValueError(COMMAND_INVALID_BILLING_DATE)

    def raise_for_invalid_authorizations(self, authorization):
        pattern = r"^AUT-(?:\d+-)*\d+$"
        failed_authorizations = []
        for a in authorization:
            if re.match(pattern, a) is None:
                failed_authorizations.append(a)
        if failed_authorizations:
            raise ValueError(f"Invalid authorizations id: {', '.join(failed_authorizations)}")

    def handle(self, *args, **options):
        year = options["year"]
        month = options["month"]
        try:
            self.raise_for_invalid_date(year, month)
        except ValueError as e:
            self.error(str(e))
            return

        authorizations: list[str] = options["authorizations"]
        try:
            self.raise_for_invalid_authorizations(authorizations)
        except ValueError as e:
            self.error(str(e))
            return

        self.info(
            f"Running {self.name} for {year}-{month:02d} "
            f"for authorizations {' '.join(authorizations)}"
        )
        self.info(f"Process {self.name} for generating journals")
        self.process(year, month, authorizations)
        self.info(
            f"Completed {self.name} for {year}-{month:02d} "
            f"for authorizations {' '.join(authorizations)}"
        )

    @staticmethod
    def process(year, month, authorizations):
        generator = BillingJournalGenerator(
            mpt_client, config, year, month, settings.MPT_PRODUCTS_IDS, authorizations
        )
        generator.generate_billing_journals()
