import datetime as dt
import re

from django.conf import settings

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
from swo_aws_extension.shared import mpt_client

config = Config()


class Command(StyledPrintCommand):
    """Generate billing journals."""

    help = "Generate Journals for monthly billing"
    name = "generate_billing_journals"

    def add_arguments(self, parser):
        """Add required arguments."""
        # Calculate last month's date
        today = dt.datetime.now(tz=dt.UTC)
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

    def raise_for_invalid_date(self, year, month):  # noqa: C901
        """Checks invalid combination of year/month."""
        current_date = dt.datetime.now(tz=dt.UTC)
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

    # TODO: not sure that we need this check
    def raise_for_invalid_authorizations(self, authorizations):
        """Checks for valid authorization id."""
        pattern = r"^AUT-(?:\d+-)*\d+$"
        failed_authorizations = [auth for auth in authorizations if not re.match(pattern, auth)]
        if failed_authorizations:
            raise ValueError(f"Invalid authorizations id: {', '.join(failed_authorizations)}")

    def handle(self, *args, **options):  # noqa: WPS110
        """Run command."""
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

    def process(self, year, month, authorizations):
        """Start billing journal processing."""
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
