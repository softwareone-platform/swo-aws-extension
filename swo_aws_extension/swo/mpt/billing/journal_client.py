import json
from functools import lru_cache
from typing import IO

from mpt_extension_sdk.mpt_http.base import MPTClient
from requests import Response

from swo_aws_extension.swo.mpt.billing.models.hints import Journal, JournalAttachment, JournalCharge
from swo_aws_extension.swo.mpt.httpquery import HttpQuery

# TODO: SDK candidate


class AttachmentsClient:
    """MPT API client to work with journal attachments."""

    def __init__(self, client: MPTClient, journal_id: str):
        self._client = client
        self.journal_id = journal_id

    def query(self, rql=None) -> HttpQuery[JournalAttachment]:
        """List attachments."""
        url = f"/billing/journals/{self.journal_id}/attachments"
        return HttpQuery(self._client, url, rql)

    def upload(
        self,
        file,
        mimetype: str,
        filename: str | None = None,
        attachment: JournalAttachment | None = None,
    ) -> JournalAttachment:
        """
        Uploads attachment files to the Journal.

        Args:
            attachment: A file-like object (supporting read operations) to be uploaded.
            filename: The name of the file to be uploaded.
            mimetype: The MIME type of the file to be uploaded.
            file: A file-like object (supporting read operations) to be uploaded.

        Returns:
            JournalAttachment: A dictionary containing the response data from the upload operation.

        Raises:
            HTTPError: If the upload request fails, an exception will be raised.
        """
        url = f"/billing/journals/{self.journal_id}/attachments"
        filename = filename or file.name
        attachment = attachment or JournalAttachment(name="", description="")

        files = {"file": (filename, file, mimetype)}
        response = self._client.post(url, data={"attachment": json.dumps(attachment)}, files=files)
        response.raise_for_status()
        return response.json()

    def get(self, attachment_id: str) -> JournalAttachment:
        """Get attachment by id."""
        response = self._client.get(
            f"/billing/journals/{self.journal_id}/attachments/{attachment_id}"
        )
        response.raise_for_status()
        return response.json()

    def delete(self, attachment_id: str):
        """Delete attachment."""
        response = self._client.delete(
            f"/billing/journals/{self.journal_id}/attachments/{attachment_id}"
        )
        response.raise_for_status()
        return response

    def all(self):
        """List all attachments, it paginates over all entries."""
        return self.query().all()


class ChargesClient:
    """Journal charges client for MPT."""

    def __init__(self, client: MPTClient, journal_id: str):
        self._client = client
        self.journal_id = journal_id

    def query(self, rql=None) -> HttpQuery[JournalCharge]:
        """List charges."""
        url = f"/billing/journals/{self.journal_id}/charges"
        return HttpQuery(self._client, url, rql)

    def all(self):
        """List all charges, it paginates over all entries."""
        return self.query().all()

    def download(self) -> Response:
        """Returns a text/csv Response with the charges information."""
        headers = {
            "Accept": "text/csv",
        }
        response = self._client.get(f"/billing/journals/{self.journal_id}/charges", headers=headers)
        response.raise_for_status()
        return response


class JournalClient:
    """Journal client for MPT."""

    def __init__(self, client: MPTClient):
        self._client = client

    def get(self, journal_id: str) -> Journal:
        """Get journal by id."""
        response = self._client.get(f"/billing/journals/{journal_id}")
        response.raise_for_status()
        return response.json()

    def create(self, journal: Journal) -> Journal:
        """
        Creates a new journal.

        Args:
            journal: the journal to create

        Returns:
            The new journal
        """
        response = self._client.post("/billing/journals", json=journal)
        response.raise_for_status()
        return response.json()

    def query(self, query=None) -> HttpQuery[Journal]:
        """List journals."""
        url = "/billing/journals"
        return HttpQuery(self._client, url, query)

    def all(self) -> list[Journal]:
        """List journals, it paginates over all entries."""
        return self.query().all()

    def update(self, journal_id: str, journal: Journal) -> Journal:
        """
        Updates journal object.

        Args:
            journal_id: MPT Journal Id
            journal: Journal data to update

        Returns:
            Updated journal

        Raises:
            HTTPError: if update fails
        """
        response = self._client.put(f"/billing/journals/{journal_id}", json=journal)
        response.raise_for_status()
        return response.json()

    def upload(self, journal_id: str, file: IO, filename: str | None = None) -> Journal:
        """
        Uploads a file associated with a specific journal.

        This method is used to upload a file to a specified journal using the given journal
        ID. The file is sent to the appropriate endpoint, which processes it as part of the
        specified journal. You can provide an optional filename and file type. If not
        provided, defaults for these values will be used.

        Args:
            journal_id: The unique identifier of the journal to which the file will be
                uploaded.
            file: A file-like object (supporting read operations) to be uploaded
                containing the jsonl with journal data
            filename: An optional string specifying the name of the file. Defaults to
                the name attribute of the file object if not provided.

        Returns:
            The Journal object.

        Raises:
            HTTPError: If the upload request fails
        """
        filename = filename or file.name
        file_type = "application/jsonl"
        journals_file = {
            "file": (filename, file, file_type),
        }
        url = f"/billing/journals/{journal_id}/upload"
        response = self._client.post(url, files=journals_file)
        response.raise_for_status()
        return response.json()

    def delete(self, journal_id: str) -> None:
        """Delete journal entry."""
        response = self._client.delete(f"/billing/journals/{journal_id}")
        response.raise_for_status()
        return response.json() if response.content else None

    def regenerate(self, journal_id: str, journal: Journal | None = None) -> Journal:
        """Regenerates journal."""
        response = self._client.post(f"/billing/journals/{journal_id}/regenerate", json=journal)
        response.raise_for_status()
        return response.json()

    def submit(self, journal_id: str, journal: Journal | None = None):
        """Submits journal."""
        response = self._client.post(f"/billing/journals/{journal_id}/submit", json=journal)
        response.raise_for_status()
        return response.json()

    def accept(self, journal_id: str, journal: Journal | None = None) -> Journal:
        """Accepts journal."""
        response = self._client.post(f"/billing/journals/{journal_id}/accept", json=journal)
        response.raise_for_status()
        return response.json()

    def inquire(self, journal_id: str, journal: Journal | None = None) -> Journal:
        """Inquires journal."""
        response = self._client.post(f"/billing/journals/{journal_id}/inquire", json=journal)
        response.raise_for_status()
        return response.json()

    @lru_cache(maxsize=10)  # noqa: B019
    def attachments(self, journal_id: str) -> AttachmentsClient:
        """Get attachments client."""
        return AttachmentsClient(self._client, journal_id)

    @lru_cache(maxsize=10)  # noqa: B019
    def charges(self, journal_id: str) -> ChargesClient:
        """Get charges client."""
        return ChargesClient(self._client, journal_id)
