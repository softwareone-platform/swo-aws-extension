from swo_aws_extension.aws.config import Config
from swo_aws_extension.flows.jobs.process_aws_invitations import AWSInvitationsProcessor
from swo_aws_extension.management.commands_helpers import StyledPrintCommand
from swo_aws_extension.shared import mpt_client

config = Config()


class Command(StyledPrintCommand):
    help = "Check AWS invitation states"
    name = "order_process_aws_invitations"

    def handle(self, *args, **options):
        self.info(f"Start processing {self.name}")
        aws_processor = AWSInvitationsProcessor(mpt_client, config)
        aws_processor.process_aws_invitations()
        self.success(f"Processing {self.name} completed.")
