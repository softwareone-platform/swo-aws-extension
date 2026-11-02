import datetime as dt
import functools

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.config import get_config

CREDENTIALS_REFRESH_MARGIN = dt.timedelta(minutes=5)


def get_apn_client() -> AWSClient:
    """
    Get the APN account client shared by the agreement sync.

    The sync runs once per process, so the client is reused for the whole run. It is rebuilt
    before its assumed-role credentials expire, because boto3 does not refresh credentials
    that are passed to it explicitly.

    Returns:
        The APN account client.
    """
    apn_client = create_apn_client()
    if _credentials_expire_soon(apn_client):
        create_apn_client.cache_clear()
        apn_client = create_apn_client()
    return apn_client


@functools.cache
def create_apn_client() -> AWSClient:
    """Create the APN account client, cached for the rest of the process."""
    config = get_config()
    return AWSClient(config, config.apn_account_id, config.apn_role_name)


def _credentials_expire_soon(apn_client: AWSClient) -> bool:
    expiration = apn_client.credentials.get("Expiration")
    if not expiration:
        return False
    refresh_deadline = dt.datetime.now(dt.UTC) + CREDENTIALS_REFRESH_MARGIN
    return expiration <= refresh_deadline
