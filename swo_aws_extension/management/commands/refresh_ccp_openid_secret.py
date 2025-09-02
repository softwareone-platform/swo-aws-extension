from swo_aws_extension.aws.config import get_config
from swo_aws_extension.management.commands_helpers import StyledPrintCommand
from swo_ccp_client.client import CCPClient


class Command(StyledPrintCommand):
    """Refresh CCP openid secret."""

    help = "Refresh CCP OpenID Secret"

    def handle(self, *args, **options):  # pragma: no cover
        """Run command."""
        self.info("Start refreshing CCP OpenID Token Secret...")
        config = get_config()
        ccp_client = CCPClient(config)
        ccp_client.refresh_secret()
        self.success("Refreshing CCP OpenID token Secret completed.")
