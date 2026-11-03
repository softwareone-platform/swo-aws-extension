import datetime as dt

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.aws.models import ChannelHandshakeServicePeriod
from swo_aws_extension.constants import (
    CHANNEL_HANDSHAKE_MINIMUM_NOTICE_DAYS,
    ChannelHandshakeStatusEnum,
)
from swo_aws_extension.logger import get_logger
from swo_aws_extension.swo.mpt.sync.apn_client import get_apn_client
from swo_aws_extension.swo.notifications.teams import TeamsNotificationManager

logger = get_logger(__name__)

SERVICE_TERM_RENEWAL_NOTE = (
    "Dear customer, your initial service term for Agreement {agreement_id} has expired, hence "
    "we are sending a new up to date service term. By accepting this service term both parties "
    "provide mutual consent to maintain the current billing relationship active and to prevent "
    "unilateral changes to it within the defined period."
)
SERVICE_TERM_RENEWAL_TITLE = "Service term renewal"


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
        handshake = get_apn_client().get_channel_handshake_by_id(relationship_id, handshake_id)
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


def send_service_term_renewal(
    agreement_id: str, pma_account_id: str, relationship_id: str
) -> str | None:
    """
    Send the client a new service term with the minimum notice period as a channel handshake.

    A service term that is still pending for the relationship is reused instead of sending
    another one, so a run after a failed agreement update doesn't send the client a duplicate.
    A failure is reported to Teams, so the next sync run can try again.

    Args:
        agreement_id: The agreement whose service term has expired.
        pma_account_id: The program management account the agreement is authorized for.
        relationship_id: The Partner Central relationship the handshake is sent for.

    Returns:
        The ID of the pending or new channel handshake, or None when it couldn't be created.
    """
    try:
        return _get_renewal_handshake_id(agreement_id, pma_account_id, relationship_id)
    except AWSError as error:
        message = f"Failed to send the new service term for relationship {relationship_id}"
        logger.exception(message)
        TeamsNotificationManager().send_exception(
            f"{agreement_id} - {SERVICE_TERM_RENEWAL_TITLE}", f"{message}: {error}"
        )
        return None


def _get_renewal_handshake_id(
    agreement_id: str, pma_account_id: str, relationship_id: str
) -> str | None:
    apn_client = get_apn_client()
    pending_handshake_id = _find_pending_handshake_id(apn_client, relationship_id)
    if pending_handshake_id:
        logger.info("Reusing pending service term channel handshake %s", pending_handshake_id)
        return pending_handshake_id
    pm_identifier = apn_client.get_program_management_id_by_account(pma_account_id)
    if not pm_identifier:
        message = f"Program management account not found for account {pma_account_id}"
        logger.warning(message)
        TeamsNotificationManager().send_warning(
            f"{agreement_id} - {SERVICE_TERM_RENEWAL_TITLE}", message
        )
        return None
    handshake = apn_client.create_channel_handshake(
        pma_identifier=pm_identifier,
        relationship_identifier=relationship_id,
        minimum_notice_days=CHANNEL_HANDSHAKE_MINIMUM_NOTICE_DAYS,
        note=SERVICE_TERM_RENEWAL_NOTE.format(agreement_id=agreement_id),
    )
    return handshake["channelHandshakeDetail"]["id"]


def _find_pending_handshake_id(apn_client: AWSClient, relationship_id: str) -> str | None:
    handshakes = apn_client.get_channel_handshakes_by_resource(relationship_id)
    return next(
        (
            handshake["id"]
            for handshake in handshakes
            if handshake.get("status") == ChannelHandshakeStatusEnum.PENDING.value
        ),
        None,
    )


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
