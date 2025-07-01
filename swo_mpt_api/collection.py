from typing import Generic, TypeVar

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import _paginated

T = TypeVar("T")


class Collection(Generic[T]):
    def __init__(self, client: MPTClient, url):
        self._client = client
        self._url = url

    def all(self, max_pages=100) -> list[T]:
        return _paginated(self._client, self._url, max_pages)

    def one(self) -> T:
        response_data = self._call(self._url)
        if len(response_data.get("data")) != 1:
            raise ValueError(f"Expected 1 item, got {len(response_data.get('data', []))}")
        return response_data.get("data", [])[0]

    def first(self) -> T:
        response_data = self._call(self._url)
        return response_data.get("data", [])[0]

    def page(self, offset=0, limit=10) -> dict:
        response = self._client.get(f"{self._url}&offset={offset}&limit={limit}")
        response.raise_for_status()
        response_data = response.json()
        return response_data

    def _call(self, url) -> dict:
        response = self._client.get(url)
        response.raise_for_status()
        response_data = response.json()
        return response_data
