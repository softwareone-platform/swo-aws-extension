from django.conf import settings
from mpt_extension_sdk.core.utils import setup_client

from swo_aws_extension.flows.jobs.invitations_report_creator import InvitationsReportCreator
from swo_aws_extension.management.commands_helpers import StyledPrintCommand


class Command(StyledPrintCommand):
    """Sync agreements command."""

    help = "Create invitations report."

    def handle(self, *args, **options):  # noqa: WPS110
        """Run command."""
        self.info("Starting creation of invitations report...")
        mpt_client = setup_client()

        InvitationsReportCreator(mpt_client, settings.MPT_PRODUCTS_IDS).create_and_notify_teams()
