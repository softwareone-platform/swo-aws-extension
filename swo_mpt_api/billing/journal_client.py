from functools import lru_cache
from typing import IO, Annotated

from mpt_extension_sdk.mpt_http.base import MPTClient
from requests import Response

from swo_mpt_api.httpquery import HttpQuery
from swo_mpt_api.models.hints import Journal, JournalAttachment, JournalCharge


class AttachmentsClient:
    def __init__(self, client: MPTClient, journal_id: str):
        self._client = client
        self.journal_id = journal_id

    def query(self, rql=None) -> HttpQuery[JournalAttachment]:
        url = f"/billing/journals/{self.journal_id}/attachments"
        return HttpQuery(self._client, url, rql)

    def upload(self, attachment: IO) -> JournalAttachment:
        response = self._client.post(
            f"/billing/journals/{self.journal_id}/attachments", files={"file": attachment}
        )
        response.raise_for_status()
        return response.json()

    def get(self, attachment_id) -> JournalAttachment:
        response = self._client.get(
            f"/billing/journals/{self.journal_id}/attachments/{attachment_id}"
        )
        response.raise_for_status()
        return response.json()

    def delete(self, attachment_id):
        response = self._client.delete(
            f"/billing/journals/{self.journal_id}/attachments/{attachment_id}"
        )
        response.raise_for_status()
        return response

    def all(self):
        return self.query().all()


class ChargesClient:
    def __init__(self, client: MPTClient, journal_id: str):
        self._client = client
        self.journal_id = journal_id

    def query(self, rql=None) -> HttpQuery[JournalCharge]:
        url = f"/billing/journals/{self.journal_id}/charges"
        return HttpQuery(self._client, url, rql)

    def all(self):
        return self.query().all()

    def download(self) -> Response:
        """
        Returns a text/csv Response with the charges information
        """
        headers = {
            "Accept": "text/csv",
        }
        response = self._client.get(f"/billing/journals/{self.journal_id}/charges", headers=headers)
        response.raise_for_status()
        return response


class JournalClient:
    def __init__(self, client: MPTClient):
        self._client = client

    def get(self, journal_id) -> Journal:
        response = self._client.get(f"/billing/journals/{journal_id}")
        response.raise_for_status()
        return response.json()

    def create(self, journal: Journal) -> Journal:
        response = self._client.post("/billing/journals", json=journal)
        response.raise_for_status()
        return response.json()

    def query(
        self, query: Annotated[str | None, "Query in RQL format"] = None
    ) -> HttpQuery[Journal]:
        url = "/billing/journals"
        return HttpQuery(self._client, url, query)

    def all(self) -> list[Journal]:
        return self.query().all()

    def update(self, journal_id, journal: Journal) -> Journal:
        response = self._client.put(f"/billing/journals/{journal_id}", json=journal)
        response.raise_for_status()
        return response.json()

    def upload(self, journal_id, journals_file: IO):
        response = self._client.post(
            f"/billing/journals/{journal_id}/upload", files={"file": journals_file}
        )
        response.raise_for_status()
        return response.json()

    def delete(self, journal_id) -> None:
        response = self._client.delete(f"/billing/journals/{journal_id}")
        response.raise_for_status()
        return response.json() if response.content else None

    def regenerate(self, journal_id, journal: Journal | None = None) -> Journal:
        response = self._client.post(f"/billing/journals/{journal_id}/regenerate", json=journal)
        response.raise_for_status()
        return response.json()

    def submit(self, journal_id, journal: Journal | None = None):
        response = self._client.post(f"/billing/journals/{journal_id}/submit", json=journal)
        response.raise_for_status()
        return response.json()

    def accept(self, journal_id, journal: Journal | None = None) -> Journal:
        response = self._client.post(f"/billing/journals/{journal_id}/accept", json=journal)
        response.raise_for_status()
        return response.json()

    def inquire(self, journal_id, journal: Journal | None = None) -> Journal:
        response = self._client.post(f"/billing/journals/{journal_id}/inquire", json=journal)
        response.raise_for_status()
        return response.json()

    @lru_cache(maxsize=10)  # noqa: B019
    def attachments(self, journal_id) -> AttachmentsClient:
        return AttachmentsClient(self._client, journal_id)

    @lru_cache(maxsize=10)  # noqa: B019
    def charges(self, journal_id) -> ChargesClient:
        return ChargesClient(self._client, journal_id)
