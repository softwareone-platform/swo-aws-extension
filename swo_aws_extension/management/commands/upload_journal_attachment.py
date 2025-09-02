import datetime as dt
import io
import os
import zipfile
from mimetypes import guess_type
from pathlib import Path

from django.core.management import CommandError
from mpt_extension_sdk.core.utils import setup_client
from requests import HTTPError

from swo_aws_extension.management.commands_helpers import StyledPrintCommand
from swo_mpt_api import MPTAPIClient
from swo_mpt_api.models.hints import JournalAttachment


class Command(StyledPrintCommand):
    """
    Upload a journal attachment file or zipped folder to the marketplace.

    swoext django upload_journal_attachment BJO-0005-0005 cloud_explorer.jsonl
    swoext django upload_journal_attachment BJO-0005-0005 export/reports-2025-03-01/

    Arguments:
        path: The file or folder to upload as attachment. In case of a folder, it will be zipped
        journal: The journal id, it will create
    """

    help = "Upload journal attachments files to MPT"

    def add_arguments(self, parser):
        """Add required arguments."""
        parser.add_argument(
            "journal", type=str, default=None, help="Existing journal ID to upload to"
        )
        parser.add_argument(
            "path",
            type=str,
            help="Path to the file to upload. If provided a folder it will zip it and upload it",
        )

    def _upload(self, journal_id, *args, **kwargs) -> JournalAttachment:
        client = setup_client()
        api = MPTAPIClient(client)
        return api.billing.journal.attachments(journal_id).upload(*args, **kwargs)

    def zip_add_path(self, zip_file, path) -> io.BytesIO:
        """Zips billing raw files."""
        for root, _dirs, files in os.walk(path):
            for file in files:
                file_path = Path(root) / file
                zip_file.write(file_path, file_path)

    def upload_zip(self, path, journal_id):
        """Upload zipped raw billing files to journal."""
        self.info(f"Zipping and Uploading `{path}` to `{journal_id}`")
        today = dt.datetime.now(tz=dt.UTC).date()
        filename = f"{journal_id}-{today.isoformat()}-{path.name}.zip"
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            self.zip_add_path(zip_file, path)

        mimetype = "application/zip"
        try:
            zip_buffer.seek(0)
            response = self._upload(
                journal_id, filename=filename, mimetype=mimetype, file=zip_buffer
            )
            self.info(str(response))
            self.success(f"Successfully uploaded zip to journal {journal_id}")
        except HTTPError as e:
            error_message = f"Error uploading zip file to journal {journal_id}: {e}"
            self.error(error_message)
            self.info(e.response.text)
            raise CommandError(error_message, returncode=3)

    def upload_file(self, path, journal_id):
        """Upload journal file to MPT API."""
        self.info(f"Uploading `{path}` to `{journal_id}`")
        filetype = guess_type(path)[0]
        self.info(f"Filetype: {filetype}")
        with path.open(encoding="utf-8") as fd:
            try:
                response = self._upload(journal_id, fd, "application/octet-stream")
                self.info(str(response))
                self.success(f"Successfully uploaded file `{path.name}` to journal {journal_id}")
            except HTTPError as e:
                self.error(f"Error uploading file to journal {journal_id}: {e}")
                self.info(e.response.text)
                if e.response:
                    raise CommandError(e.response.text, returncode=3)
                raise CommandError(str(e), returncode=3)

    def handle(self, *args, **options):
        """Run command."""
        journal_id = options["journal"]
        path = Path(options["path"])

        if path.is_dir():
            self.upload_zip(path, journal_id)
        elif path.is_file():
            self.upload_file(path, journal_id)
        else:
            self.error(f"Path `{path}` does not exist")
            raise CommandError(f"Path `{path}` does not exist", returncode=2)
