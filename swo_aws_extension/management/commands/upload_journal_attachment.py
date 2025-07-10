import io
import os
import pathlib
import zipfile
from datetime import date

from django.utils.timezone import override
from mpt_extension_sdk.core.utils import setup_client
from requests import HTTPError

from swo_aws_extension.management.commands_helpers import StyledPrintCommand
from swo_mpt_api import MPTAPIClient
from swo_mpt_api.models.hints import JournalAttachment


class Command(StyledPrintCommand):
    """
    Upload a journal attachment file or zipped folder to the marketplace

    Arguments:
        path: The file or folder to upload as attachment. In case of a folder, it will be zipped
        journal: The journal id, it will create

    Example:
        swoext django upload_journal_attachment BJO-0005-0005 cloud_explorer.jsonl
        swoext django upload_journal_attachment BJO-0005-0005 export/reports-2025-03-01/
    """

    help = "Upload journal attachments files to MPT"


    def add_arguments(self, parser):
        parser.add_argument(
            "journal", type=str, default=None, help="Existing journal ID to upload to"
        )
        parser.add_argument(
            "path",
            type=str,
            help="Path to the file to upload. If provided a folder it will zip it and upload it",
        )

    def _upload(self, journal_id, files) -> JournalAttachment:
        client = setup_client()
        api = MPTAPIClient(client)
        return api.billing.journal.attachments(journal_id).upload(files)

    def zip_add_path(self, zip, path) -> io.BytesIO:
        with zipfile.ZipFile(zip, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for root, _dirs, files in os.walk(path):
                for file in files:
                    file_path = os.path.join(root, file)
                    self.info(f"Zipping file: {file_path}")
                    zip_file.write(file_path, file)
                    # Calculate relative path to maintain folder structure
                    arcname = os.path.relpath(file_path, path)
                    zip_file.write(file_path, arcname)



    def upload_zip(self, path, journal_id):
        self.info(f"Zipping and Uploading `{path}` to `{journal_id}`")
        filename = f"{journal_id}-{date.today().isoformat()}-{pathlib.Path(path).name}.zip"
        zip_buffer = io.BytesIO()
        self.zip_add_path(zip_buffer, path)
        zip_buffer.seek(0)
        files = {"archive": (filename, zip_buffer, "application/zip")}
        try:
            response = self._upload(journal_id, files)
            self.info(str(response))
            self.success(f"Successfully uploaded zip to journal {journal_id}")
        except HTTPError as e:
            self.error(f"Error uploading zip file to journal {journal_id}: {e}")
            return

    def upload_file(self, path, journal_id):
        self.info(f"Uploading `{path}` to `{journal_id}`")
        filename = f"{journal_id}-{date.today().isoformat()}-{pathlib.Path(path).name}.zip"
        with open(path) as fd:
            files = {"archive": (filename, fd, "application/zip")}
            try:
                response = self._upload(journal_id, files)
                self.info(str(response))
                self.success(f"Successfully uploaded zip to journal {journal_id}")
            except HTTPError as e:
                self.error(f"Error uploading file to journal {journal_id}: {e}")
                return

    def handle(self, *args, **options):

        journal_id = options["journal"]
        path = options["path"]

        if pathlib.Path(path).is_dir():
            self.upload_zip(path, journal_id)
        elif pathlib.Path(path).is_file():
            self.upload_file(path, journal_id)
        else:
            self.error(f"Path `{path}` does not exist")
