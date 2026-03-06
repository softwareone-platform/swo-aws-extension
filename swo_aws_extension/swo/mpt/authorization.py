from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import _paginated  # noqa: PLC2701

from swo_aws_extension.swo.rql.query_builder import RQLQuery


# TODO: SDK candidate and should use dependency injection for mpt_client
def get_authorizations(
    mpt_client: MPTClient, rql_query: RQLQuery | None, limit: int = 10
) -> list[dict]:  # pragma: no cover
    """
    Retrieve authorizations based on the provided RQL query.

    Args:
        mpt_client (MPTClient): MPT API client instance.
        rql_query (RQLQuery | None): Query to filter authorizations, or None for no filter.
        limit (int): Maximum number of authorizations to retrieve.

    Returns:
        list[dict]: List of authorizations.
    """
    url = (
        f"/catalog/authorizations?{rql_query}&select=externalIds,product"
        if rql_query
        else "/catalog/authorizations?select=externalIds,product"
    )
    return _paginated(mpt_client, url, limit=limit)
