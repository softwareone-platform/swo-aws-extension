import datetime as dt
from functools import cache

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.config import get_config
from swo_aws_extension.constants import ResponsibilityTransferStatus

AVAILABLE_TRANSFER_STATUSES = frozenset((
    ResponsibilityTransferStatus.ACCEPTED.value,
    ResponsibilityTransferStatus.WITHDRAWN.value,
))


def transfer_has_ended(transfer: dict) -> bool:
    """Whether the transfer has an end date that has already been reached."""
    end_date = transfer.get("EndTimestamp")
    return bool(end_date) and end_date <= dt.datetime.now(dt.UTC)


def select_transfer(current: dict | None, candidate: dict) -> dict:
    """Pick the transfer that represents a source account when there is more than one.

    An ACCEPTED transfer always wins over WITHDRAWN ones; between WITHDRAWN transfers
    the one with the latest end date wins.
    """
    if current is None:
        return candidate
    accepted = ResponsibilityTransferStatus.ACCEPTED.value
    if current["Status"] == accepted:
        return current
    if candidate["Status"] == accepted:
        return candidate
    current_end = current.get("EndTimestamp")
    candidate_end = candidate.get("EndTimestamp")
    if candidate_end and (not current_end or candidate_end > current_end):
        return candidate
    return current


@cache
def get_available_responsibility_transfers(pma_account_id: str) -> dict:
    """Fetches ongoing inbound responsibility transfers from the specified AWS client.

    Ongoing transfers are the ACCEPTED ones plus the WITHDRAWN ones, because a withdrawn
    transfer keeps running until its end date is reached. When a source account has more
    than one transfer, the ACCEPTED one takes precedence and, among WITHDRAWN ones, only
    the one with the latest end date is kept.

    Args:
        pma_account_id: The PMA account ID to query transfers from.

    Returns:
        A dict mapping source ManagementAccountId to the ongoing transfer info.
    """
    config = get_config()
    aws_client = AWSClient(config, pma_account_id, config.management_role_name)
    result = {}
    for rt in aws_client.get_inbound_responsibility_transfers():
        if rt.get("Status") not in AVAILABLE_TRANSFER_STATUSES:
            continue
        source_account_id = rt.get("Source", {}).get("ManagementAccountId")
        if not source_account_id:
            continue
        result[source_account_id] = select_transfer(
            result.get(source_account_id),
            {
                "Id": rt["Id"],
                "Status": rt["Status"],
                "EndTimestamp": rt.get("EndTimestamp"),
            },
        )

    return result


def get_available_transfer_for_account(
    pma_account_id: str, source_management_account_id: str
) -> dict | None:
    """
    Get the ongoing inbound responsibility transfer for a specific source account.

    Ongoing transfers are the ACCEPTED ones plus the WITHDRAWN ones that keep running
    until their end date is reached.

    Args:
        pma_account_id: The PMA account ID to query transfers from.
        source_management_account_id: The source ManagementAccountId to filter by.

    Returns:
        The ongoing transfer dict if found, None otherwise.
    """
    available_transfers = get_available_responsibility_transfers(pma_account_id)
    return available_transfers.get(source_management_account_id)
