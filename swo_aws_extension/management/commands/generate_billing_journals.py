import datetime as dt
import re
from decimal import Decimal

from django.conf import settings
from mpt_extension_sdk.core.utils import setup_client

from swo_aws_extension.config import get_config
from swo_aws_extension.constants import (
    COMMAND_INVALID_BILLING_DATE,
    COMMAND_INVALID_BILLING_DATE_FUTURE,
)
from swo_aws_extension.flows.jobs.billing_journal.billing_journal_service import (
    BillingJournalService,
)
from swo_aws_extension.flows.jobs.billing_journal.models.billing_period import BillingPeriod
from swo_aws_extension.flows.jobs.billing_journal.models.context import BillingJournalContext
from swo_aws_extension.management.commands_helpers import StyledPrintCommand
from swo_aws_extension.swo.mpt.billing.billing_client import BillingClient
from swo_aws_extension.swo.notifications.teams import TeamsNotificationManager

MIN_BILLING_YEAR = 2025
MAX_MONTH = 12
MIN_BILLING_DAY = 5
AUTH_PATTERN = re.compile(r"^AUT-(?:\d+-)*\d+$")


class Command(StyledPrintCommand):
    """Generate Journals for monthly billing."""

    help = "Generate Journals for monthly billing"
    name = "generate_billing_journals"

    def add_arguments(self, parser):
        """Add required arguments."""
        today = dt.datetime.now(tz=dt.UTC)
        default_year = today.year - 1 if today.month == 1 else today.year
        default_month = MAX_MONTH if today.month == 1 else today.month - 1

        parser.add_argument(
            "--year",
            type=int,
            default=default_year,
            help=f"Year for billing (default: {default_year})",
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
            help="list of specific authorizations separated by space",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Generate journals in dry_run mode without uploading to MPT",
        )

    def handle(self, *args, **options):  # noqa: WPS110 WPS210
        """Run command."""
        year, month = options["year"], options["month"]
        authorizations = options["authorizations"]

        error = self.validate(year, month, authorizations)
        if error:
            self.error(error)
            return

        auth_str = " ".join(authorizations) if authorizations else "all"
        formatted_month = str(month).zfill(2)
        period = f"{year}-{formatted_month}"
        self.info(f"Start {self.name} for {period} ({auth_str})")

        config = get_config()
        notifier = TeamsNotificationManager()
        billing_period = BillingPeriod.from_year_month(year, month)

        client = setup_client()
        job_context = BillingJournalContext(
            mpt_client=client,
            billing_api_client=BillingClient(client),
            config=config,
            billing_period=billing_period,
            product_ids=settings.MPT_PRODUCTS_IDS,
            notifier=notifier,
            authorizations=authorizations,
            pls_charge_percentage=Decimal(str(config.pls_charge_percentage)),
            dry_run=options.get("dry_run", False),
        )
        service = BillingJournalService(job_context)
        service.run()

        self.success(f"Completed {self.name} for {period}.")

    def validate(
        self,
        year: int,
        month: int,
        authorizations: list,
    ) -> str | None:
        """Validate command parameters. Returns error message or None if valid."""
        error = self._validate_year_month(year, month)
        if error:
            return error

        invalid = [auth for auth in authorizations if not AUTH_PATTERN.match(auth)]
        if invalid:
            invalid_str = ", ".join(invalid)
            return f"Invalid authorizations id: {invalid_str}"

        return None

    def _validate_year_month(self, year: int, month: int) -> str | None:
        if year < MIN_BILLING_YEAR:
            return f"Year must be {MIN_BILLING_YEAR} or higher, got {year}"

        if not 1 <= month <= MAX_MONTH:
            return f"Invalid month. Must be between 1 and {MAX_MONTH}. Got {month}."

        now = dt.datetime.now(tz=dt.UTC)
        is_future = year > now.year
        if not is_future and year == now.year and month >= now.month:
            is_future = True

        if is_future:
            return COMMAND_INVALID_BILLING_DATE_FUTURE

        prev_year = now.year - 1 if now.month == 1 else now.year
        prev_month = MAX_MONTH if now.month == 1 else now.month - 1

        if year == prev_year and month == prev_month and now.day < MIN_BILLING_DAY:
            return COMMAND_INVALID_BILLING_DATE

        return None
