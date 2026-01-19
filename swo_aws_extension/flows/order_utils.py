import copy
import logging

from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import (
    complete_order,
    fail_order,
    get_product_template_or_default,
    query_order,
    update_order,
)
from mpt_extension_sdk.mpt_http.wrap_http_error import MPTError, wrap_mpt_http_error

from swo_aws_extension.constants import MptOrderStatus
from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.steps.errors import OrderStatusChangeError
from swo_aws_extension.notifications import MPTNotificationManager

logger = logging.getLogger(__name__)
MPT_ORDER_STATUS_QUERYING = "Querying"
MPT_ORDER_STATUS_PROCESSING = "Processing"
MPT_ORDER_STATUS_COMPLETED = "Completed"


def set_template(order, template):
    """Set the template in the order."""
    updated_order = copy.deepcopy(order)
    updated_order["template"] = template
    return updated_order


# TODO: SDK candidate
@wrap_mpt_http_error
def process_order(client: MPTClient, order_id: str, **kwargs):  # pragma: no cover
    """Update the order status to PROCESS."""
    response = client.post(
        f"/commerce/orders/{order_id}/process",
        json=kwargs,
    )
    response.raise_for_status()
    return response.json()


def set_order_template(
    client: MPTClient, context: InitialAWSContext, status: str, template_name: str
):
    """Get the rendered template from MPT API."""
    template = get_product_template_or_default(
        client,
        context.order["product"]["id"],
        status,
        template_name,
    )
    found_template_name = template.get("name")
    if found_template_name != template_name:
        logger.info(
            "%s - Template error - Template template_name=`%s` not found for status `%s`. "
            "Using template_name=`%s` instead. Please check the template name and template setup"
            " in the MPT platform.",
            context.order_id,
            template_name,
            status,
            found_template_name,
        )
    context.order = set_template(context.order, template)
    logger.info("%s - Action - Updated template to %s", context.order_id, template_name)
    return context.order


def switch_order_status_to_query_and_notify(
    client: MPTClient, context: InitialAWSContext, template_name: str
):
    """Switch the order status to 'Querying' if it is not already in that status."""
    context.order = set_order_template(client, context, MPT_ORDER_STATUS_QUERYING, template_name)
    kwargs = {
        "parameters": context.order["parameters"],
        "template": context.template,
    }
    if context.order.get("error"):
        kwargs["error"] = context.order["error"]

    context.order = query_order(
        client,
        context.order_id,
        **kwargs,
    )
    MPTNotificationManager(client).send_notification(context)


def switch_order_status_to_failed_and_notify(
    client: MPTClient, context: InitialAWSContext, error: str
):
    """Switch the order status to 'Failed'."""
    kwargs = {
        "parameters": context.order["parameters"],
    }

    context.order = fail_order(
        client,
        context.order_id,
        error,
        **kwargs,
    )
    MPTNotificationManager(client).send_notification(context)


def switch_order_status_to_process_and_notify(
    client: MPTClient, context: InitialAWSContext, template_name: str
):
    """Switch the order status to 'Processing'."""
    context.order = set_order_template(client, context, MPT_ORDER_STATUS_PROCESSING, template_name)
    kwargs = {
        "parameters": context.order["parameters"],
        "template": context.template,
    }
    try:
        context.order = process_order(
            client,
            context.order_id,
            **kwargs,
        )
    except MPTError as error:
        logger.info(
            "%s - Cannot switch order to 'Processing': %s",
            context.order_id,
            error,
        )
        return
    MPTNotificationManager(client).send_notification(context)


def switch_order_status_to_complete_and_notify(
    client: MPTClient, context: InitialAWSContext, template_name: str
):
    """Updates the order status to completed."""
    if context.order_status == MptOrderStatus.COMPLETED:
        raise OrderStatusChangeError(
            current_status=context.order_status, target_status=MptOrderStatus.COMPLETED
        )
    context.order = set_order_template(client, context, MPT_ORDER_STATUS_COMPLETED, template_name)
    kwargs = {
        "parameters": context.order["parameters"],
        "template": context.template,
    }

    context.order = complete_order(client, context.order_id, **kwargs)
    MPTNotificationManager(client).send_notification(context)
    logger.info("%s - Action - Set order to completed", context.order_id)


def update_processing_template_and_notify(
    client: MPTClient, context: InitialAWSContext, template_name: str
):
    """Update the order parameters and template from a template name."""
    context.order = set_order_template(client, context, MPT_ORDER_STATUS_PROCESSING, template_name)

    kwargs = {
        "parameters": context.order["parameters"],
        "template": context.template,
    }

    context.order = update_order(client, context.order_id, **kwargs)
    MPTNotificationManager(client).send_notification(context)
