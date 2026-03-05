from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import _paginated  # noqa: PLC2701


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
