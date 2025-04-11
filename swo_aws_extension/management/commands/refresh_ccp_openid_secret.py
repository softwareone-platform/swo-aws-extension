from django.core.management.base import BaseCommand

from swo_aws_extension.key_vault.ccp import refresh_ccp_openid_secret


class Command(BaseCommand):
    help = "Refresh CCP OpenID Secret"

    def success(self, message):
        self.stdout.write(self.style.SUCCESS(message), ending="\n")

    def info(self, message):
        self.stdout.write(message, ending="\n")

    def warning(self, message):
        self.stdout.write(self.style.WARNING(message), ending="\n")

    def error(self, message):
        self.stderr.write(self.style.ERROR(message), ending="\n")

    def handle(self, *args, **options):
        self.info("Start refreshing CCP OpenID Token Secret...")
        refresh_ccp_openid_secret()
        self.success("Refreshing CCP OpenID token Secret completed.")
