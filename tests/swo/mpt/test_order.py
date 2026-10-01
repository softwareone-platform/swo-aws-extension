import pytest

from swo_aws_extension.swo.mpt.order import ORDERS_QUERY_BATCH_SIZE, get_orders_by_ids


@pytest.fixture
def mock_get_orders_by_query(mocker):
    return mocker.patch("swo_aws_extension.swo.mpt.order.get_orders_by_query", return_value=[])


def test_get_orders_by_ids_returns_orders_keyed_by_id(mpt_client, mock_get_orders_by_query):
    mock_get_orders_by_query.return_value = [{"id": "ORD-1"}, {"id": "ORD-2"}]

    result = get_orders_by_ids(mpt_client, ["ORD-1", "ORD-2", "ORD-3"], "select=audit")

    assert result == {"ORD-1": {"id": "ORD-1"}, "ORD-2": {"id": "ORD-2"}}
    mock_get_orders_by_query.assert_called_once_with(
        mpt_client, "in(id,(ORD-1,ORD-2,ORD-3))&select=audit", limit=ORDERS_QUERY_BATCH_SIZE
    )


def test_get_orders_by_ids_queries_in_batches(mpt_client, mock_get_orders_by_query):
    order_ids = [f"ORD-{index}" for index in range(ORDERS_QUERY_BATCH_SIZE + 1)]

    get_orders_by_ids(mpt_client, order_ids, "select=audit")  # act

    assert mock_get_orders_by_query.call_count == 2
    last_query = mock_get_orders_by_query.call_args.args[1]
    assert last_query == f"in(id,(ORD-{ORDERS_QUERY_BATCH_SIZE}))&select=audit"


def test_get_orders_by_ids_without_ids_does_not_query(mpt_client, mock_get_orders_by_query):
    result = get_orders_by_ids(mpt_client, [], "select=audit")

    assert result == {}
    mock_get_orders_by_query.assert_not_called()
