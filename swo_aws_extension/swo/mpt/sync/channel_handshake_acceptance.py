from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.constants import ChannelHandshakeStatusEnum
from swo_aws_extension.logger import get_logger
from swo_aws_extension.swo.mpt.sync.apn_client import get_apn_client

logger = get_logger(__name__)


def is_channel_handshake_accepted(relationship_id: str, handshake_id: str) -> bool:
    """
    Check whether the client accepted a channel handshake.

    Args:
        relationship_id: The Partner Central relationship the handshake belongs to.
        handshake_id: The channel handshake ID.

    Returns:
        True when the handshake is accepted, False when it isn't or can't be read.
    """
    try:
        handshake = get_apn_client().get_channel_handshake_by_id(relationship_id, handshake_id)
    except AWSError:
        logger.exception("Failed to get channel handshake %s", handshake_id)
        return False
    if not handshake:
        logger.warning(
            "Channel handshake %s not found for relationship %s", handshake_id, relationship_id
        )
        return False
    return handshake.get("status") == ChannelHandshakeStatusEnum.ACCEPTED.value
