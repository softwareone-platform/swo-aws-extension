from itertools import batched
from typing import Any

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import _paginated  # ruff:ignore[import-private-name]

from swo_aws_extension.swo.rql.query_builder import RQLQuery

ORDERS_QUERY_BATCH_SIZE = 50


# TODO: SDK candidate and should use dependency injection for mpt_client
def get_orders_by_query(
    mpt_client: MPTClient, query: str, limit: int = 10
) -> list[dict]:  # pragma: no cover
    """
    This method is used to get the orders by query.

    Args:
        mpt_client (MPTClient): MPT API client instance.
        query (str): Query to filter orders.
        limit (int): Maximum number of orders to retrieve.

    Returns:
        list[dict]: List of orders.
    """
    url = f"/commerce/orders?{query}"
    return _paginated(mpt_client, url, limit=limit)


def get_orders_by_ids(
    mpt_client: MPTClient, order_ids: list[str], select: str
) -> dict[str, dict[str, Any]]:
    """
    Get the orders with the given ids, keyed by order id.

    The orders are fetched with one RQL ``in`` query per batch of ``ORDERS_QUERY_BATCH_SIZE``
    ids. Orders that no longer exist in the marketplace are missing from the result.

    Args:
        mpt_client (MPTClient): MPT API client instance.
        order_ids (list[str]): Ids of the orders to fetch.
        select (str): Select clause appended to each query, for example ``select=audit``.

    Returns:
        dict[str, dict[str, Any]]: Orders found, keyed by id.
    """
    orders: dict[str, dict[str, Any]] = {}
    for order_ids_batch in batched(order_ids, ORDERS_QUERY_BATCH_SIZE):
        query = f"{RQLQuery(id__in=list(order_ids_batch))}&{select}"
        for order in get_orders_by_query(mpt_client, query, limit=ORDERS_QUERY_BATCH_SIZE):
            orders[order["id"]] = order
    return orders
