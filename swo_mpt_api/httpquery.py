from typing import Annotated, Generic, Self, TypeVar

from mpt_extension_sdk.mpt_http.base import MPTClient

T = TypeVar("T")


class HttpQuery(Generic[T]):
    def __init__(self, client: MPTClient, url: str, query=None):
        self._client = client
        self._url = url
        self._query = query

    def _has_more_pages(self, page):
        if not page:
            return True
        pagination = page["$meta"]["pagination"]
        return pagination["total"] > pagination["limit"] + pagination["offset"]

    def _paginated(self, limit=10):
        items = []
        page = None
        offset = 0
        while self._has_more_pages(page):
            page = self.page(offset, limit)
            items.extend(page["data"])
            offset += limit
        return items

    def all(self) -> list[T]:
        return self._paginated()

    def one(self) -> T:
        response_data = self._call(self._url)
        if len(response_data.get("data")) != 1:
            raise ValueError(f"Expected 1 item, got {len(response_data.get('data', []))}")
        return response_data.get("data", [])[0]

    def first(self) -> T:
        response_data = self._call(self._url)
        return response_data.get("data", [])[0]

    def page(self, offset=0, limit=10) -> dict:
        response_data = self._call(f"offset={offset}&limit={limit}")
        return response_data

    def query(self, query: Annotated[str, None, "Query in RQL format"]) -> Self:
        if self._query and query:
            query = f"{self._query}&{query}"
        elif self._query or query:
            query = self._query or query
        return HttpQuery(self._client, self._url, query)

    def _call(self, query=None) -> dict:
        url = self._url
        query_parts = []
        if self._query:
            query_parts.append(self._query)
        if query:
            query_parts.append(query)
        if query_parts:
            full_query = "&".join(query_parts)
            response = self._client.get(f"{url}?{full_query}")
        else:
            response = self._client.get(url)
        response.raise_for_status()
        response_data = response.json()
        return response_data
