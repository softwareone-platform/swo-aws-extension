import logging

from mpt_extension_sdk.mpt_http.utils import find_first
from requests import HTTPError

from swo_aws_extension.airtable.models import (
    MPAStatusEnum,
    NotificationStatusEnum,
    NotificationTypeEnum,
    create_pool_notification,
    get_mpa_accounts,
    get_notifications_by_status,
    get_open_notifications,
)
from swo_aws_extension.constants import (
    CRM_EMPTY_ADDITIONAL_INFO,
    CRM_EMPTY_SUMMARY,
    CRM_EMPTY_TITLE,
    CRM_NOTIFICATION_ADDITIONAL_INFO,
    CRM_NOTIFICATION_SUMMARY,
    CRM_NOTIFICATION_TITLE,
    CRM_TICKET_RESOLVED_STATE,
    SupportTypesEnum,
)
from swo_crm_service_client import ServiceRequest
from swo_crm_service_client.client import get_service_client

logger = logging.getLogger(__name__)


def process_pending_notification(crm_client, pending_notification):
    """
    Process a pending notification.

    Args:
        crm_client: The CRM client.
        pending_notification: The pending notification to process.
    """
    logger.info("Processing pending notification %s", pending_notification.notification_id)
    try:
        ticket = crm_client.get_service_requests(None, pending_notification.ticket_id)
    except HTTPError:
        logger.exception(
            "Failed to fetch ticket %s for pending notification %s",
            pending_notification.ticket_id,
            pending_notification.notification_id,
        )
        return
    ticket_state = ticket.get("state", "")

    if ticket_state in CRM_TICKET_RESOLVED_STATE:
        pending_notification.ticket_state = ticket_state
        pending_notification.status = NotificationStatusEnum.DONE.value
        pending_notification.save()
        logger.info("Ticket %s is completed.", pending_notification.ticket_id)
    elif ticket_state != pending_notification.ticket_state:
        pending_notification.ticket_state = ticket_state
        pending_notification.save()
        logger.info("Ticket %s state updated to %s.", pending_notification.ticket_id, ticket_state)
    else:
        logger.info(
            "Pending Notification %s is still pending.",
            pending_notification.notification_id,
        )


def create_ticket(crm_client, notification, summary, title, additional_info):
    """
    Create a new notification.

    Args:
        crm_client: The CRM client.
        notification: Notification data.
        summary: The summary of the notification.
        title: The title of the notification.
        additional_info: Additional information for the notification.
    """
    logger.info(
        "New service request ticket will be created for country %s with PLS enabled: %s "
        "and type: %s.",
        notification.country,
        notification.pls_enabled,
        notification.notification_type,
    )
    service_request = ServiceRequest(additional_info=additional_info, summary=summary, title=title)
    ticket = crm_client.create_service_request(None, service_request)
    logger.info("Service request ticket created with id: %s", ticket.get("id", ""))
    return ticket


def delete_duplicated_new_notifications(open_notifications, pending_notifications):  # noqa: C901
    """Delete duplicated notifications."""
    unique_notifications = []
    notifications_map = {}

    for notification in open_notifications:
        if notification.status != NotificationStatusEnum.NEW:
            continue
        existing_notification = find_first(
            lambda pending, ntf=notification: pending.country == ntf.country
            and pending.pls_enabled == ntf.pls_enabled,
            pending_notifications,
        )
        if existing_notification:
            notification.delete()
            logger.info("Duplicated pending notification %s deleted.", notification.notification_id)
            continue

        if notification.country not in notifications_map:
            notifications_map[notification.country] = {}
        if notification.pls_enabled in notifications_map[notification.country]:
            notification.delete()
            logger.info("Duplicated new notification %s deleted.", notification.notification_id)
        else:
            notifications_map[notification.country][notification.pls_enabled] = True

            if not existing_notification:
                unique_notifications.append(notification)
    return unique_notifications


def add_new_notifications(minimum_mpa_threshold, accounts_map, open_notifications):
    """Add new notifications based on the accounts map."""
    for country, pls_map in accounts_map.items():
        for pls_enabled, count_accounts in pls_map.items():
            if count_accounts > int(minimum_mpa_threshold):
                continue
            existing_notification = find_first(
                lambda pending, country_value=country, pls_value=pls_enabled: pending.country
                == country_value
                and pending.pls_enabled == pls_value,
                open_notifications,
            )
            if existing_notification:
                logger.info(
                    "Pending notification already exists for PLS enabled: %s and country %s.",
                    pls_enabled,
                    country,
                )

                continue
            notification_type = (
                NotificationTypeEnum.EMPTY.value
                if count_accounts == 0
                else NotificationTypeEnum.WARNING.value
            )
            new_notification = {
                "status": NotificationStatusEnum.NEW.value,
                "notification_type": notification_type,
                "pls_enabled": pls_enabled,
                "country": country,
            }
            create_pool_notification(new_notification)
            logger.info(
                "New notification created for country %s with PLS enabled: %s.",
                country,
                pls_enabled,
            )


def get_mpa_accounts_map():
    """Get the MPA accounts map."""
    mpa_accounts = get_mpa_accounts()
    accounts_map = {}
    for mpa_account in mpa_accounts:
        if mpa_account.country not in accounts_map:
            accounts_map[mpa_account.country] = {
                True: 0,
                False: 0,
            }
        if mpa_account.status == MPAStatusEnum.READY:
            accounts_map[mpa_account.country][mpa_account.pls_enabled] += 1
    return accounts_map


def check_pool_accounts_notifications(config) -> None:
    """Check the pool accounts notifications."""
    crm_client = get_service_client()
    open_notifications = get_open_notifications()
    pending_notifications = [
        notification
        for notification in open_notifications
        if notification.status == NotificationStatusEnum.PENDING
    ]

    for pending_notification in pending_notifications:
        process_pending_notification(crm_client, pending_notification)

    logger.info("Check if new notifications need to be created")

    delete_duplicated_new_notifications(open_notifications, pending_notifications)
    accounts_map = get_mpa_accounts_map()
    add_new_notifications(config.minimum_mpa_threshold, accounts_map, pending_notifications)

    logger.info("Proceed to create new ticket if needed")
    new_notifications = get_notifications_by_status(NotificationStatusEnum.NEW.value)
    for notification in new_notifications:
        if notification.notification_type == NotificationTypeEnum.EMPTY:
            summary = CRM_EMPTY_SUMMARY.format(
                type_of_support=SupportTypesEnum.PARTNER_LED_SUPPORT.value
                if notification.pls_enabled
                else SupportTypesEnum.RESOLD_SUPPORT.value,
                seller_country=notification.country,
            )
            ticket = create_ticket(
                crm_client,
                notification,
                summary,
                CRM_EMPTY_TITLE.format(region=notification.country),
                CRM_EMPTY_ADDITIONAL_INFO,
            )
        else:
            summary = CRM_NOTIFICATION_SUMMARY.format(
                type_of_support=SupportTypesEnum.PARTNER_LED_SUPPORT.value
                if notification.pls_enabled
                else SupportTypesEnum.RESOLD_SUPPORT.value,
                seller_country=notification.country,
            )
            ticket = create_ticket(
                crm_client,
                notification,
                summary,
                CRM_NOTIFICATION_TITLE.format(region=notification.country),
                CRM_NOTIFICATION_ADDITIONAL_INFO,
            )

        notification.status = NotificationStatusEnum.PENDING.value
        notification.ticket_state = "New"
        notification.ticket_id = ticket.get("id", "")
        notification.save()

    logger.info("Pool accounts notifications checked")
