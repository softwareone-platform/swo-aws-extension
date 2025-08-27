from collections import UserDict
from unittest.mock import MagicMock

import pytest

from swo_mpt_api.httpquery import HttpQuery


class DummyModel(UserDict):
    """Dummy model for tests purpuse only."""


def test_one_returns_single_item():
    mock_client = MagicMock()
    expected_item = DummyModel({"id": 1, "name": "test"})
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": [expected_item]}
    mock_response.raise_for_status.return_value = None
    mock_client.get.return_value = mock_response
    collection = HttpQuery[DummyModel](mock_client, "http://fake-url")
    result = collection.one()
    assert result == expected_item


def test_one_raises_if_not_one_item():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": [{"id": 1}, {"id": 2}]}
    mock_response.raise_for_status.return_value = None
    mock_client.get.return_value = mock_response
    collection = HttpQuery[DummyModel](mock_client, "http://fake-url")

    with pytest.raises(ValueError):
        collection.one()


def test_first_returns_first_item():
    mock_client = MagicMock()
    expected_item = DummyModel({"id": 1, "name": "first"})
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": [expected_item, {"id": 2}]}
    mock_response.raise_for_status.return_value = None
    mock_client.get.return_value = mock_response
    collection = HttpQuery[DummyModel](mock_client, "http://fake-url")

    result = collection.first()

    assert result == expected_item


def test_page_returns_response_data():
    mock_client = MagicMock()
    expected_data = {"data": [{"id": 1}, {"id": 2}], "meta": {"total": 2}}
    mock_response = MagicMock()
    mock_response.json.return_value = expected_data
    mock_response.raise_for_status.return_value = None
    mock_client.get.return_value = mock_response
    collection = HttpQuery[DummyModel](mock_client, "http://fake-url")

    result = collection.page(offset=5, limit=2)

    mock_client.get.assert_called_once_with("http://fake-url?offset=5&limit=2")
    assert result == expected_data


def test_query_combines_existing_and_new_rql():
    mock_client = MagicMock()
    base_query = "foo=1"
    new_rql = "bar=2"
    hq = HttpQuery(mock_client, "http://fake-url", base_query)
    result = hq.query(new_rql)
    assert isinstance(result, HttpQuery)
    assert result._query == f"{base_query}&{new_rql}"  # noqa: SLF001
    assert result._url == "http://fake-url"  # noqa: SLF001
    assert result._client == mock_client  # noqa: SLF001


def test_query_uses_existing_query_only():
    mock_client = MagicMock()
    base_query = "foo=1"
    hq = HttpQuery(mock_client, "http://fake-url", base_query)
    result = hq.query(None)
    assert result._query == base_query  # noqa: SLF001


def test_query_uses_new_rql_only():
    mock_client = MagicMock()
    new_rql = "bar=2"
    hq = HttpQuery(mock_client, "http://fake-url")
    result = hq.query(new_rql)
    assert result._query == new_rql  # noqa: SLF001


def test_query_with_no_query_or_rql():
    mock_client = MagicMock()
    hq = HttpQuery(mock_client, "http://fake-url")
    result = hq.query(None)
    assert result._query is None  # noqa: SLF001


def test__call_no_query():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": [1]}
    mock_response.raise_for_status.return_value = None
    mock_client.get.return_value = mock_response
    hq = HttpQuery(mock_client, "http://fake-url")
    result = hq._call()  # noqa: SLF001
    mock_client.get.assert_called_once_with("http://fake-url")
    mock_response.raise_for_status.assert_called_once()
    assert result == {"data": [1]}


def test__call_with_self_query():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": [2]}
    mock_response.raise_for_status.return_value = None
    mock_client.get.return_value = mock_response
    hq = HttpQuery(mock_client, "http://fake-url", "foo=1")
    result = hq._call()  # noqa: SLF001
    mock_client.get.assert_called_once_with("http://fake-url?foo=1")
    assert result == {"data": [2]}


def test__call_with_query_arg():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": [3]}
    mock_response.raise_for_status.return_value = None
    mock_client.get.return_value = mock_response
    hq = HttpQuery(mock_client, "http://fake-url")
    result = hq._call(query="bar=2")  # noqa: SLF001
    mock_client.get.assert_called_once_with("http://fake-url?bar=2")
    assert result == {"data": [3]}


def test__call_with_both_queries():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": [4]}
    mock_response.raise_for_status.return_value = None
    mock_client.get.return_value = mock_response
    hq = HttpQuery(mock_client, "http://fake-url", "foo=1")
    result = hq._call(query="bar=2")  # noqa: SLF001
    mock_client.get.assert_called_once_with("http://fake-url?foo=1&bar=2")
    assert result == {"data": [4]}
