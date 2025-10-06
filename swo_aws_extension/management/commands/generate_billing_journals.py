import re
from datetime import datetime

from django.conf import settings
from mpt_extension_sdk.core.utils import setup_client

from swo_aws_extension.aws.config import Config
from swo_aws_extension.constants import (
    COMMAND_INVALID_BILLING_DATE,
    COMMAND_INVALID_BILLING_DATE_FUTURE,
)
from swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator import (
    BillingJournalGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.processor_dispatcher import (
    JournalProcessorDispatcher,
)
from swo_aws_extension.management.commands_helpers import StyledPrintCommand

config = Config()


class Command(StyledPrintCommand):
    help = "Generate Journals for monthly billing"
    name = "generate_billing_journals"

    def add_arguments(self, parser):
        # Calculate last month's date
        today = datetime.now()
        year = today.year
        month = today.month

        if month == 1:
            default_month = 12
            default_year = year - 1
        else:
            default_month = month - 1
            default_year = year

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

    @staticmethod
    def raise_for_invalid_date(year, month):
        current_date = datetime.now()
        current_year, current_month, current_day = (
            current_date.year,
            current_date.month,
            current_date.day,
        )

        if year < 2025:
            raise ValueError(f"Year must be 2025 or higher, got {year}")

        if month < 1 or month > 12:
            raise ValueError(f"Invalid month. Month must be between 1 and 12. Got {month} instead.")

        if current_date.month == month and current_date.year == year:
            raise ValueError(COMMAND_INVALID_BILLING_DATE)

        if current_month == 1:
            prev_month, prev_year = 12, current_year - 1
        else:
            prev_month, prev_year = current_month - 1, current_year

        if year == prev_year and month == prev_month and current_day < 5:
            raise ValueError(COMMAND_INVALID_BILLING_DATE)

        if (year > current_year) or (year == current_year and month > current_month):
            raise ValueError(COMMAND_INVALID_BILLING_DATE_FUTURE)

    def raise_for_invalid_authorizations(self, authorization):
        pattern = r"^AUT-(?:\d+-)*\d+$"
        failed_authorizations = []
        for a in authorization:
            if re.match(pattern, a) is None:
                failed_authorizations.append(a)
        if failed_authorizations:
            raise ValueError(f"Invalid authorizations id: {", ".join(failed_authorizations)}")

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
            f"for authorizations {" ".join(authorizations)}"
        )
        self.info(f"Process {self.name} for generating journals")
        self.process(year, month, authorizations)
        self.info(
            f"Completed {self.name} for {year}-{month:02d} "
            f"for authorizations {" ".join(authorizations)}"
        )

    @staticmethod
    def process(year, month, authorizations):
        mpt_client = setup_client()
        generator = BillingJournalGenerator(
            mpt_client,
            config,
            year,
            month,
            settings.MPT_PRODUCTS_IDS,
            JournalProcessorDispatcher.build(config),
            authorizations,
        )
        generator.generate_billing_journals()
