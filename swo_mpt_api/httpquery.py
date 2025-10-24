from typing import Annotated, Self

from mpt_extension_sdk.mpt_http.base import MPTClient


class HttpQuery[T]:
    """MPT API Query wrapper."""

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
        """Paginate over all entries and return whole list from the API."""
        return self._paginated()

    def one(self) -> T:
        """Get only one entry from the API."""
        response_data = self._call(self._url)
        if len(response_data.get("data")) != 1:
            raise ValueError(f"Expected 1 item, got {len(response_data.get('data', []))}")
        return response_data.get("data", [])[0]

    def first(self) -> T:
        """Get first entry from the API."""
        response_data = self._call(self._url)
        return response_data.get("data", [])[0]

    def page(self, offset=0, limit=10) -> dict:
        """Retrieve particular page from the MPT API."""
        return self._call(f"offset={offset}&limit={limit}")

    def query(self, query: Annotated[str, None, "Query in RQL format"]) -> Self:
        """Apply RQL query to the HTTP query."""
        if self._query and query:
            query = f"{self._query}&{query}"
        elif self._query or query:
            query = self._query or query
        return HttpQuery(self._client, self._url, query)

    def _call(self, query=None) -> dict:
        url = self._url
        query_parts = []
        if self._query:
            query_parts.append(str(self._query))
        if query:
            query_parts.append(str(query))
        if query_parts:
            full_query = "&".join(query_parts)
            response = self._client.get(f"{url}?{full_query}")
        else:
            response = self._client.get(url)
        response.raise_for_status()
        return response.json()
