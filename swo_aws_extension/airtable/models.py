from dataclasses import dataclass
from enum import StrEnum
from functools import cache

from django.conf import settings
from pyairtable.formulas import AND, EQUAL, FIELD, STR_VALUE
from pyairtable.orm import Model, fields
from requests import HTTPError


class MPAStatusEnum(StrEnum):
    READY = "Ready"
    ASSIGNED = "Assigned"
    ERROR = "Error"


class NotificationTypeEnum(StrEnum):
    EMPTY = "Empty"
    WARNING = "Warning"


class NotificationTicketStatusEnum(StrEnum):
    NOT_CREATED = "Not Created"
    CREATED = "Ticket Created"
    CLOSED = "Ticket Closed"


class NotificationStatusEnum(StrEnum):
    PENDING = "Pending"
    IN_PROGRESS = "In Progress"
    DONE = "Done"


PLS_ENABLED = "PLS Enabled"


@dataclass(frozen=True)
class AirTableBaseInfo:
    api_key: str
    base_id: str

    @staticmethod
    def for_mpa_pool():
        """
        Returns an AirTableBaseInfo object with the base identifier of the base that
        contains the MPA pool tables and the API key.

        Args:

        Returns:
            AirTableBaseInfo: The base info.
        """
        return AirTableBaseInfo(
            api_key=settings.EXTENSION_CONFIG["AIRTABLE_API_TOKEN"],
            base_id=settings.EXTENSION_CONFIG["AIRTABLE_BASES"],
        )


@cache
def get_master_payer_account_pool_model(base_info):
    """
    Returns the MPAPool model class connected to the right base and with
    the right API key.

    Args:
        base_info (AirTableBaseInfo): The base info instance.

    Returns:
        Transfer: The AirTable MPAPool model.
    """

    class MPAPool(Model):
        account_id = fields.TextField("Account Id")
        account_email = fields.TextField("Account Email")
        account_name = fields.TextField("Account Name")
        pls_enabled = fields.CheckboxField(PLS_ENABLED)
        status = fields.SelectField("Status")
        agreement_id = fields.TextField("Agreement Id")
        client_id = fields.TextField("Client Id")
        scu = fields.TextField("SCU")
        error_description = fields.TextField("Error Description")

        class Meta:
            table_name = "Master Payer Accounts"
            api_key = base_info.api_key
            base_id = base_info.base_id

    return MPAPool


@cache
def get_pool_notification_model(base_info):
    """
    Returns the PoolNotification model class connected to the right base and with
    the right API key.

    Args:
        base_info (AirTableBaseInfo): The base info instance.

    Returns:
        Transfer: The AirTable PoolNotification model.
    """

    class PoolNotification(Model):
        notification_id = fields.NumberField("Id")
        notification_type = fields.SelectField("Notification Type")
        pls_enabled = fields.CheckboxField(PLS_ENABLED)
        ticket_id = fields.TextField("Ticket Id")
        ticket_status = fields.SelectField("Ticket Status")
        status = fields.SelectField("Status")

        class Meta:
            table_name = "Pool Notifications"
            api_key = base_info.api_key
            base_id = base_info.base_id

    return PoolNotification


def get_available_mpa_from_pool(pls_enabled=False):
    """
    Returns the available MPAs from the pool for a given region.
    Args:
        pls_enabled (bool): Whether the MPA is activated in PLS.

    Returns:
        list: The available MPAs.

    """
    mpa_pool = get_master_payer_account_pool_model(AirTableBaseInfo.for_mpa_pool())

    return mpa_pool.all(
        formula=AND(
            FIELD(PLS_ENABLED) if pls_enabled else f"NOT({FIELD(PLS_ENABLED)})",
            EQUAL(FIELD("Status"), STR_VALUE(MPAStatusEnum.READY)),
        )
    )


def get_pending_notifications():
    """
    Returns the pending notifications from the pool.
    Returns:
        list: The pending notifications.
    """
    pool_notification = get_pool_notification_model(AirTableBaseInfo.for_mpa_pool())
    return pool_notification.all(EQUAL("Status", NotificationStatusEnum.PENDING))


def get_in_progress_notifications():
    """
    Returns the in progress notifications from the pool.
    Returns:
        list: The in progress notifications.
    """
    pool_notification = get_pool_notification_model(AirTableBaseInfo.for_mpa_pool())
    return pool_notification.all(EQUAL("Status", NotificationStatusEnum.IN_PROGRESS))


def get_mpa_view_link():
    """
    Generate a link to a record of the Master Payer Accounts table in the AirTable UI.

    Returns:
        str: The link to the Master Payer Accounts record or None in case of an error.
    """
    try:
        mpa_pool = get_master_payer_account_pool_model(AirTableBaseInfo.for_mpa_pool())
        base_id = mpa_pool.Meta.base_id
        table_id = mpa_pool.get_table().id
        view_id = mpa_pool.get_table().schema().view("Master Payer Accounts").id
        record_id = mpa_pool.id
        return f"https://airtable.com/{base_id}/{table_id}/{view_id}/{record_id}"
    except HTTPError:
        pass
