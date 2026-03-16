import logging

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import update_order

from swo_aws_extension.config import Config
from swo_aws_extension.constants import SupportTypesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.crm_tickets.templates.deploy_services_error import (
    DEPLOY_SERVICES_ERROR_TEMPLATE,
)
from swo_aws_extension.flows.steps.crm_tickets.ticket_manager import TicketManager
from swo_aws_extension.flows.steps.errors import UnexpectedStopError
from swo_aws_extension.parameters import (
    get_feature_version_deployment_error_notified,
    get_formatted_supplementary_services,
    get_formatted_technical_contact,
    get_mpa_account_id,
    get_support_type,
    set_feature_version_deployment_error_notified,
)
from swo_aws_extension.swo.notifications.email import EmailNotificationManager
from swo_aws_extension.swo.notifications.templates.deploy_services_feature import (
    DEPLOY_SERVICES_FEATURE_TEMPLATE,
)
from swo_aws_extension.swo.notifications.templates.deploy_services_feature_error import (
    DEPLOY_SERVICES_FEATURE_ERROR_TEMPLATE,
)

logger = logging.getLogger(__name__)


def _get_deploy_services_context(context: PurchaseContext) -> dict:
    contact = get_formatted_technical_contact(context.order)
    return {
        "customer_name": context.buyer.get("name"),
        "buyer_id": context.buyer.get("id"),
        "buyer_external_id": context.buyer.get("externalIds", {}).get("erpCustomer", ""),
        "pm_account_id": context.pm_account_id,
        "order_id": context.order_id,
        "master_payer_id": get_mpa_account_id(context.order),
        "technical_contact_name": contact["name"],
        "technical_contact_email": contact["email"],
        "technical_contact_phone": contact["phone"],
        "support_type": get_support_type(context.order),
        "supplementary_services": get_formatted_supplementary_services(context.order),
    }


def send_error_ticket(config: Config, context: PurchaseContext, error_message: str) -> None:
    """Send a CRM ticket for a deployment error, logging a warning if ticket creation fails."""
    summary = DEPLOY_SERVICES_ERROR_TEMPLATE.summary.format(
        **_get_deploy_services_context(context), error_message=error_message
    )
    try:
        TicketManager(
            config, "Deploy Services Error", DEPLOY_SERVICES_ERROR_TEMPLATE
        ).create_new_ticket(context, summary)
    except UnexpectedStopError:
        logger.warning("%s - Failed to create deploy services error ticket", context.order_id)


def get_deploy_services_email_body(context: PurchaseContext) -> str:
    """Build the deploy services feature email body."""
    return DEPLOY_SERVICES_FEATURE_TEMPLATE.body.format(**_get_deploy_services_context(context))


def get_deploy_services_error_email_body(context: PurchaseContext, error_message: str) -> str:
    """Build the deploy services error email body."""
    return DEPLOY_SERVICES_FEATURE_ERROR_TEMPLATE.body.format(
        **_get_deploy_services_context(context), error_message=error_message
    )


def send_services_email(
    config: Config, context: PurchaseContext, body: str, log_message: str
) -> None:
    """Send the deploy services feature email notification."""
    if EmailNotificationManager(config).send_email(
        config.deploy_services_feature_recipients,
        DEPLOY_SERVICES_FEATURE_TEMPLATE.subject,
        body,
    ):
        logger.info("%s - %s", context.order_id, log_message)


# In-process deduplication guard: the API flag (`featureVersionDeploymentErrorNotified`)
# prevents duplicate emails across process restarts, but has propagation delay (~1-10s).
# This set ensures no duplicate emails are sent within the same process lifetime while
# the API update propagates.
# Note: This assumes single-threaded, process-based isolation (one consumer process per pod).
# No synchronization is needed under this deployment model.
notified_order_ids: set[str] = set()


def handle_error(
    context: PurchaseContext,
    config: Config,
    client: MPTClient,
    error_title: str,
    error_details: str,
    log_message: str,
) -> None:
    """Helper function to handle errors in flows."""
    is_notified = get_feature_version_deployment_error_notified(context.order)
    support_type = get_support_type(context.order)

    if is_notified != "yes" and context.order_id not in notified_order_ids:
        context.order = set_feature_version_deployment_error_notified(context.order, "yes")
        context.order = update_order(
            client, context.order_id, parameters=context.order["parameters"]
        )
        notified_order_ids.add(context.order_id)
        body = get_deploy_services_error_email_body(context, error_details)
        send_services_email(config, context, body, log_message)
        logger.info("%s - Action - Error email sent", context.order_id)

    if support_type == SupportTypesEnum.PARTNER_LED_SUPPORT.value:
        raise UnexpectedStopError(error_title, error_details)
