from swo_aws_extension.config import get_config
from swo_aws_extension.management.commands_helpers import StyledPrintCommand
from swo_aws_extension.swo.ccp.client import CCPClient


class Command(StyledPrintCommand):
    """Refresh CCP openid secret."""

    help = "Refresh CCP OpenID Secret"

    def handle(self, *args, **options):  # noqa: WPS110  # pragma: no cover
        """Run command."""
        self.info("Start refreshing CCP OpenID Token Secret...")
        config = get_config()
        ccp_client = CCPClient(config)
        ccp_client.refresh_secret()
        self.success("Refreshing CCP OpenID token Secret completed.")
