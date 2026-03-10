from collections import UserDict
from unittest.mock import MagicMock

import pytest

from swo_aws_extension.swo.mpt.httpquery import HttpQuery


class DummyModel(UserDict):
    """Dummy model for HttpQuery generic testing."""


def test_init():
    mock_client = MagicMock()
    url = "https://fake-url"
    query = "fake=query"

    result = HttpQuery(mock_client, url, query)

    assert result._client == mock_client  # noqa: SLF001
    assert result._url == url  # noqa: SLF001
    assert result._query == query  # noqa: SLF001


def test_has_more_pages_no_page():
    mock_client = MagicMock()
    hq = HttpQuery(mock_client, "https://fake-url")

    result = hq._has_more_pages(None)  # noqa: SLF001

    assert result is True


def test_has_more_pages_with_more():
    mock_client = MagicMock()
    hq = HttpQuery(mock_client, "https://fake-url")
    page = {"$meta": {"pagination": {"total": 20, "limit": 10, "offset": 0}}}

    result = hq._has_more_pages(page)  # noqa: SLF001

    assert result is True


def test_has_more_pages_with_no_more():
    mock_client = MagicMock()
    hq = HttpQuery(mock_client, "https://fake-url")
    page = {"$meta": {"pagination": {"total": 20, "limit": 10, "offset": 10}}}

    result = hq._has_more_pages(page)  # noqa: SLF001

    assert result is False


def test_page_returns_response_data():
    mock_client = MagicMock()
    item_data = [{"id": 1}, {"id": 2}]
    meta_data = {"total": 2}
    expected_data = {"data": item_data, "meta": meta_data}
    mock_response = MagicMock()
    mock_response.json.return_value = expected_data
    mock_response.raise_for_status.return_value = None
    mock_client.get.return_value = mock_response
    hq = HttpQuery(mock_client, "https://fake-url")

    result = hq.page(0, 10)

    mock_client.get.assert_called_once_with("https://fake-url?offset=0&limit=10")
    assert result == expected_data


def test_all_returns_paginated_data():
    mock_client = MagicMock()
    first_mock = MagicMock()
    first_mock.json.return_value = {
        "data": [{"id": 1}],
        "$meta": {"pagination": {"total": 2, "limit": 1, "offset": 0}},
    }
    second_mock = MagicMock()
    second_mock.json.return_value = {
        "data": [{"id": 2}],
        "$meta": {"pagination": {"total": 2, "limit": 1, "offset": 1}},
    }
    mock_client.get.side_effect = [first_mock, second_mock]
    hq = HttpQuery(mock_client, "https://fake-url")

    result = hq.all()

    assert mock_client.get.call_count == 2
    assert result == [{"id": 1}, {"id": 2}]


def test_query_combines_existing_and_new_rql():
    mock_client = MagicMock()
    base_query = "foo=1"
    new_rql = "bar=2"
    hq = HttpQuery(mock_client, "https://fake-url", base_query)

    result = hq.query(new_rql)

    assert isinstance(result, HttpQuery)
    assert result._query == f"{base_query}&{new_rql}"  # noqa: SLF001
    assert result._url == "https://fake-url"  # noqa: SLF001
    assert result._client == mock_client  # noqa: SLF001


def test_query_uses_new_rql_if_none_exists():
    mock_client = MagicMock()
    new_rql = "bar=2"
    hq = HttpQuery(mock_client, "https://fake-url")

    result = hq.query(new_rql)

    assert isinstance(result, HttpQuery)
    assert result._query == new_rql  # noqa: SLF001


def test_query_ignores_none_rql():
    mock_client = MagicMock()
    base_query = "foo=1"
    hq = HttpQuery(mock_client, "https://fake-url", base_query)

    result = hq.query(None)

    assert isinstance(result, HttpQuery)
    assert result._query == base_query  # noqa: SLF001


def test_query_none_on_none():
    mock_client = MagicMock()
    hq = HttpQuery(mock_client, "https://fake-url")

    result = hq.query(None)

    assert isinstance(result, HttpQuery)
    assert result._query is None  # noqa: SLF001


def test_call_no_query():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": [1]}
    mock_response.raise_for_status.return_value = None
    mock_client.get.return_value = mock_response
    hq = HttpQuery(mock_client, "https://fake-url")

    result = hq._call()  # noqa: SLF001

    mock_client.get.assert_called_once_with("https://fake-url")
    mock_response.raise_for_status.assert_called_once()
    assert result == {"data": [1]}


def test_call_with_self_query():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": [2]}
    mock_response.raise_for_status.return_value = None
    mock_client.get.return_value = mock_response
    hq = HttpQuery(mock_client, "https://fake-url", "a=1")

    result = hq._call()  # noqa: SLF001

    mock_client.get.assert_called_once_with("https://fake-url?a=1")
    assert result == {"data": [2]}


def test_call_with_query_arg():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": [3]}
    mock_response.raise_for_status.return_value = None
    mock_client.get.return_value = mock_response
    hq = HttpQuery(mock_client, "https://fake-url")

    result = hq._call("b=2")  # noqa: SLF001

    mock_client.get.assert_called_once_with("https://fake-url?b=2")
    assert result == {"data": [3]}


def test_call_with_both_queries():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": [4]}
    mock_response.raise_for_status.return_value = None
    mock_client.get.return_value = mock_response
    hq = HttpQuery(mock_client, "https://fake-url", "a=1")

    result = hq._call("b=2")  # noqa: SLF001

    mock_client.get.assert_called_once_with("https://fake-url?a=1&b=2")
    assert result == {"data": [4]}


def test_first():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": [{"id": 1}, {"id": 2}]}
    mock_response.raise_for_status.return_value = None
    mock_client.get.return_value = mock_response
    hq = HttpQuery(mock_client, "https://fake-url")

    result = hq.first()

    assert result == {"id": 1}


def test_one_success():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": [{"id": 1}]}
    mock_response.raise_for_status.return_value = None
    mock_client.get.return_value = mock_response
    hq = HttpQuery(mock_client, "https://fake-url")

    result = hq.one()

    assert result == {"id": 1}


def test_one_raises_value_error_if_multiple():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": [{"id": 1}, {"id": 2}]}
    mock_response.raise_for_status.return_value = None
    mock_client.get.return_value = mock_response
    hq = HttpQuery(mock_client, "https://fake-url")

    with pytest.raises(ValueError, match="Expected 1 item, got 2"):
        hq.one()


def test_one_raises_value_error_if_empty():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": []}
    mock_response.raise_for_status.return_value = None
    mock_client.get.return_value = mock_response
    hq = HttpQuery(mock_client, "https://fake-url")

    with pytest.raises(ValueError, match="Expected 1 item, got 0"):
        hq.one()
