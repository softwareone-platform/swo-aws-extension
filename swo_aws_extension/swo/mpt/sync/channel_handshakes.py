import datetime as dt
import functools

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.aws.models import ChannelHandshakeServicePeriod
from swo_aws_extension.config import get_config
from swo_aws_extension.constants import ChannelHandshakeStatusEnum
from swo_aws_extension.logger import get_logger
from swo_aws_extension.swo.notifications.teams import TeamsNotificationManager

logger = get_logger(__name__)

CREDENTIALS_REFRESH_MARGIN = dt.timedelta(minutes=5)


def get_fixed_commitment_end_date(
    agreement_id: str, relationship_id: str, handshake_id: str
) -> dt.date | None:
    """
    Get the end date of the fixed commitment period agreed in a channel handshake.

    A missing handshake, or a fixed commitment without an end date, is reported to Teams.

    Args:
        agreement_id: The agreement the handshake belongs to, used in the Teams warning.
        relationship_id: The Partner Central relationship the handshake belongs to.
        handshake_id: The channel handshake ID.

    Returns:
        The last day of the fixed commitment period, or None when the handshake can't be
        read, doesn't exist, isn't accepted, or doesn't hold a fixed commitment period.
    """
    try:
        handshake = _get_apn_client().get_channel_handshake_by_id(relationship_id, handshake_id)
    except AWSError:
        logger.exception("Failed to get channel handshake %s", handshake_id)
        return None
    if not handshake:
        _warn(
            agreement_id,
            f"Channel handshake {handshake_id} not found for relationship {relationship_id}",
        )
        return None
    if handshake.get("status") != ChannelHandshakeStatusEnum.ACCEPTED.value:
        logger.info("Channel handshake %s is not accepted, skipping", handshake_id)
        return None
    service_period = _get_service_period(handshake, handshake_id)
    if not service_period or not service_period.is_fixed_commitment():
        return None
    return _get_commitment_end_date(agreement_id, service_period, handshake_id)


def _get_commitment_end_date(
    agreement_id: str, service_period: ChannelHandshakeServicePeriod, handshake_id: str
) -> dt.date | None:
    if service_period.end_date:
        return service_period.end_date.date()
    _warn(
        agreement_id,
        f"Channel handshake {handshake_id} has a fixed commitment period without an end date",
    )
    return None


def _warn(agreement_id: str, message: str) -> None:
    logger.warning(message)
    TeamsNotificationManager().send_warning(
        f"{agreement_id} - Synchronize handshake expiration date", message
    )


def _get_apn_client() -> AWSClient:
    # The sync runs once per process, so the client is reused for the whole run. It is
    # rebuilt before its assumed-role credentials expire, because boto3 does not refresh
    # credentials that are passed to it explicitly.
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


def _get_service_period(handshake: dict, handshake_id: str) -> ChannelHandshakeServicePeriod | None:
    try:
        return ChannelHandshakeServicePeriod.from_handshake(handshake)
    except (TypeError, ValueError) as error:
        logger.warning(
            "Invalid service period in channel handshake %s (%s); the next sync tries again",
            handshake_id,
            error,
        )
        return None
