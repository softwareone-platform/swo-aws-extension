import logging

from swo_aws_extension.airtable.models import (
    NotificationStatusEnum,
    NotificationTypeEnum,
    create_pool_notification,
    get_available_mpa_from_pool,
    get_pending_notifications,
    has_pending_notifications,
)
from swo_aws_extension.constants import (
    CRM_TICKET_RESOLVED_STATE,
    EMPTY_SUMMARY,
    EMPTY_TITLE,
    NOTIFICATION_SUMMARY,
    NOTIFICATION_TITLE,
)
from swo_aws_extension.crm_service_client import get_service_client
from swo_crm_service_client import ServiceRequest

logger = logging.getLogger(__name__)


def process_pending_notification(crm_client, pending_notification):
    """
    Process a pending notification.

    Args:
        crm_client: The CRM client.
        pending_notification: The pending notification to process.
    """
    logger.info(f"Processing pending notification {pending_notification.notification_id}")
    ticket = crm_client.get_service_requests(None, pending_notification.ticket_id)
    ticket_state = ticket.get("state", "")

    if ticket_state in CRM_TICKET_RESOLVED_STATE:
        pending_notification.ticket_state = ticket_state
        pending_notification.status = NotificationStatusEnum.DONE
        pending_notification.save()
        logger.info(f"Ticket {pending_notification.ticket_id} is completed.")
    elif ticket_state != pending_notification.ticket_state:
        pending_notification.ticket_state = ticket_state
        pending_notification.save()
        logger.info(f"Ticket {pending_notification.ticket_id} state updated to {ticket_state}.")
    else:
        logger.info(
            f"Pending Notification {pending_notification.notification_id} is still pending."
        )


def create_new_notification(crm_client, pls_enabled, notification_type, summary, title):
    """
    Create a new notification.

    Args:
        crm_client: The CRM client.
        pls_enabled: Whether PLS is enabled.
        notification_type: The type of notification.
        summary: The summary of the notification.
        title: The title of the notification.
    """
    logger.info(
        f"New service request ticket will be created with PLS enabled: {pls_enabled} "
        f"and type: {notification_type}"
    )
    service_request = ServiceRequest(
        external_user_email="test@example.com",
        external_username="test@example.com",
        requester="Supplier.Portal",
        sub_service="Service Activation",
        global_academic_ext_user_id="globalacademicExtUserId",
        additional_info="AWS Master Payer account",
        summary=summary,
        title=title,
        service_type="MarketPlaceServiceActivation",
    )
    ticket = crm_client.create_service_request(None, service_request)
    logger.info(f"Service request ticket created with id: {ticket.get('id', '')}")
    pending_notification = {
        "ticket_id": ticket.get("id", ""),
        "ticket_state": "New",
        "status": NotificationStatusEnum.PENDING,
        "notification_type": notification_type,
        "pls_enabled": pls_enabled,
    }
    create_pool_notification(pending_notification)
    logger.info(f"Airtable Pending notifications created for PLS enabled: {pls_enabled}")


def check_pool_accounts_notifications() -> None:
    """
    Check the pool accounts notifications.
    """
    pls_values = [True, False]
    crm_client = get_service_client()

    pending_notifications = get_pending_notifications()
    for pending_notification in pending_notifications:
        process_pending_notification(crm_client, pending_notification)

    logger.info("Check if new notifications need to be created")
    for pls_enabled in pls_values:
        if has_pending_notifications(pls_enabled):
            logger.info(
                f"Pending notification found for PLS {'enabled' if pls_enabled else 'disabled'}"
            )
            continue

        available_mpa = get_available_mpa_from_pool(pls_enabled)
        if not available_mpa:
            create_new_notification(
                crm_client, pls_enabled, NotificationTypeEnum.EMPTY, EMPTY_SUMMARY, EMPTY_TITLE
            )
        elif len(available_mpa) <= 3:
            create_new_notification(
                crm_client,
                pls_enabled,
                NotificationTypeEnum.WARNING,
                NOTIFICATION_SUMMARY,
                NOTIFICATION_TITLE,
            )

    logger.info("Pool accounts notifications checked")
