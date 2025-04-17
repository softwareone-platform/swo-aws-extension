from django.core.management.base import BaseCommand

from swo_aws_extension.aws.config import Config
from swo_aws_extension.flows.jobs.process_aws_invitations import AWSInvitationsProcessor

config = Config()


class Command(BaseCommand):
    help = "Check AWS invitation states"
    name = "order_process_aws_invitations"

    def success(self, message):
        self.stdout.write(self.style.SUCCESS(message), ending="\n")

    def info(self, message):
        self.stdout.write(message, ending="\n")

    def warning(self, message):
        self.stdout.write(self.style.WARNING(message), ending="\n")

    def error(self, message):
        self.stderr.write(self.style.ERROR(message), ending="\n")

    def handle(self, *args, **options):
        self.info(f"Start processing {self.name}")
        aws_processor = AWSInvitationsProcessor(config)
        aws_processor.process_aws_invitations()
        self.success(f"Processing {self.name} completed.")
