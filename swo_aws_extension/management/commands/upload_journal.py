import argparse
import datetime as dt

from mpt_extension_sdk.core.utils import setup_client
from requests.exceptions import HTTPError

from swo_aws_extension.management.commands_helpers import StyledPrintCommand
from swo_mpt_api import MPTAPIClient
from swo_mpt_api.models.hints import Journal


class Command(StyledPrintCommand):
    """
    Upload a journal file to the marketplace.

    Upload a journal file to the marketplace by providing authorization id or journal id
    swoext django upload_journal --authorization AUT-0001-0001 journal_lines.jsonl
    swoext django upload_journal --journal BJO-0005-0005 journal_lines.jsonl

    Args:
        file: The jsonl file to upload
        authorization: Optional - The authorization id, it will create
        journal: Optional - The journal id, it will create
    """

    help = "Upload journal file to MPT"

    def add_arguments(self, parser):
        """Add required arguments."""
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--authorization", help="Authorization ID to create a new journal")
        group.add_argument(
            "--journal", type=str, default=None, help="Existing journal ID to upload to"
        )
        parser.add_argument(
            "file", type=argparse.FileType("r"), help="Path to the journal file to upload"
        )

    def handle(self, *args, **options):
        """Run command."""
        file = options["file"]
        authorization = options["authorization"]
        journal_id = options["journal"]

        client = setup_client()
        api = MPTAPIClient(client)

        if not journal_id:
            now = dt.datetime.now(tz=dt.UTC)
            journal_data = Journal(
                authorization={"id": authorization},
                name=f"{now.strftime('%Y-%m-%d')} - Manual upload - {file.name}",
            )
            self.info(
                f"Creating journal for authorization "
                f"{journal_data['authorization']['id']} with name `{journal_data['name']}` ..."
            )
            try:
                journal = api.billing.journal.create(journal_data)
            except HTTPError as ex:
                self.error(f"Unable to create a journal due to an HTTP Error: {ex}")
                self.info(f"Request: {ex.request}")
                self.error(ex.response.text)
                return

            journal_id = journal["id"]
            self.success(f"Created journal {journal_id} for authorization {authorization}.")
        self.info(f"Start fileupload {file.name} for authorization {journal_id}...")
        try:
            updated_journal = api.billing.journal.upload(journal_id, file)
        except HTTPError as ex:
            self.error(f"Unable to upload journal due to an HTTP Error: {ex}")
            self.info(f"Request: {ex.request}")
            self.error(ex.response.text)
            return
        self.info(
            f"Uploaded `{file.name}` to journal {journal_id}. "
            f"Status: `{updated_journal['status']}` "
            f"Processing Total: `{updated_journal['processing']['total']}`"
        )
        self.success(f"File upload {file.name} for authorization {journal_id} completed.")
