from django.core.management.base import BaseCommand

from swo_aws_extension.aws.config import get_config
from swo_ccp_client.client import CCPClient


class Command(BaseCommand):
    help = "Refresh CCP OpenID Secret"

    def success(self, message):  # pragma: no cover
        self.stdout.write(self.style.SUCCESS(message), ending="\n")

    def info(self, message):  # pragma: no cover
        self.stdout.write(message, ending="\n")

    def warning(self, message):  # pragma: no cover
        self.stdout.write(self.style.WARNING(message), ending="\n")

    def error(self, message):  # pragma: no cover
        self.stderr.write(self.style.ERROR(message), ending="\n")

    def handle(self, *args, **options):  # pragma: no cover
        self.info("Start refreshing CCP OpenID Token Secret...")
        config = get_config()
        ccp_client = CCPClient(config)
        ccp_client.refresh_secret()
        self.success("Refreshing CCP OpenID token Secret completed.")
