import functools
import logging
import os
from dataclasses import dataclass
from datetime import datetime

import boto3
import pymsteams
from django.conf import settings
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markdown_it import MarkdownIt
from mpt_extension_sdk.mpt_http.mpt import get_rendered_template

from swo_aws_extension.parameters import OrderParametersEnum, get_ordering_parameter

logger = logging.getLogger(__name__)


def dateformat(date_string):
    return datetime.fromisoformat(date_string).strftime("%-d %B %Y") if date_string else ""


env = Environment(
    loader=FileSystemLoader(
        os.path.join(
            os.path.abspath(os.path.dirname(__file__)),
            "templates",
        ),
    ),
    autoescape=select_autoescape(),
)

env.filters["dateformat"] = dateformat


@dataclass
class Button:
    label: str
    url: str


@dataclass
class FactsSection:
    title: str
    data: dict


def send_notification(
    title: str,
    text: str,
    color: str,
    button: Button | None = None,
    facts: FactsSection | None = None,
) -> None:
    message = pymsteams.connectorcard(settings.EXTENSION_CONFIG["MSTEAMS_WEBHOOK_URL"])
    message.color(color)
    message.title(title)
    message.text(text)
    if button:
        message.addLinkButton(button.label, button.url)
    if facts:
        facts_section = pymsteams.cardsection()
        facts_section.title(facts.title)
        for key, value in facts.data.items():
            facts_section.addFact(key, value)
        message.addSection(facts_section)

    try:
        message.send()
    except pymsteams.TeamsWebhookException:
        logger.exception("Error sending notification to MSTeams!")


def send_warning(
    title: str,
    text: str,
    button: Button | None = None,
    facts: FactsSection | None = None,
) -> None:
    send_notification(
        f"\u2622 {title}",
        text,
        "#ffa500",
        button=button,
        facts=facts,
    )


def send_error(
    title: str,
    text: str,
    button: Button | None = None,
    facts: FactsSection | None = None,
) -> None:
    send_notification(
        f"\U0001f4a3 {title}",
        text,
        "#df3422",
        button=button,
        facts=facts,
    )


def send_exception(
    title: str,
    text: str,
    button: Button | None = None,
    facts: FactsSection | None = None,
) -> None:
    send_notification(
        f"\U0001f525 {title}",
        text,
        "#541c2e",
        button=button,
        facts=facts,
    )


def send_email(recipient, subject, template_name, context):
    template = env.get_template(f"{template_name}.html")
    rendered_email = template.render(context)

    access_key, secret_key = settings.EXTENSION_CONFIG["AWS_SES_CREDENTIALS"].split(":")

    client = boto3.client(
        "ses",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=settings.EXTENSION_CONFIG["AWS_SES_REGION"],
    )
    try:
        client.send_email(
            Source=settings.EXTENSION_CONFIG["EMAIL_NOTIFICATIONS_SENDER"],
            Destination={
                "ToAddresses": recipient,
            },
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Html": {"Data": rendered_email, "Charset": "UTF-8"},
                },
            },
        )
    except Exception:
        logger.exception(
            f"Cannot send notification email with subject '{subject}' to: {recipient}",
        )


def get_notifications_recipient(order, buyer):
    return (get_ordering_parameter(order, OrderParametersEnum.CONTACT).get("value", {}) or {}).get(
        "email"
    ) or (buyer.get("contact", {}) or {}).get("email")


def md2html(template):
    md = MarkdownIt("commonmark", {"breaks": True, "html": True})

    def custom_h1_renderer(tokens, idx, options, env):
        tokens[idx].attrSet("style", "line-height: 1.2em;")
        return md.renderer.renderToken(tokens, idx, options, env)

    md.renderer.rules["heading_open"] = custom_h1_renderer

    return md.render(template)


def send_email_notification(client, order, buyer):
    """
    Send a notification email to the customer according to the
    current order status.
    It embeds the current order template into the email body.

    Args:
        client (MPTClient): The client used to consume the
        MPT API.
        order (dict): The order for which the notification should be sent.
        buyer (dict): The buyer of the order.
    """
    email_notification_enabled = bool(
        settings.EXTENSION_CONFIG.get("EMAIL_NOTIFICATIONS_ENABLED", False)
    )
    order_id = order.get("id")

    if not email_notification_enabled:
        logger.info(f"{order_id} - Skip - Email notification is disabled")
        return

    recipient = get_notifications_recipient(order, buyer)
    if not recipient:
        logger.warning(f"Cannot send email notifications for order {order_id}: no recipient found")
        return

    context = {
        "order": order,
        "activation_template": md2html(get_rendered_template(client, order["id"])),
        "api_base_url": settings.MPT_API_BASE_URL,
        "portal_base_url": settings.MPT_PORTAL_BASE_URL,
    }
    subject = f"Order status update {order_id} for {order['buyer']['name']}"
    if order["status"] == "Querying":
        subject = f"This order need your attention {order_id} for {order['buyer']['name']}"
    send_email(
        [recipient],
        subject,
        "email",
        context,
    )
    logger.info(f"{order_id} - Action - Email sent to {recipient} - {subject}")


@functools.cache
def notify_unhandled_exception_in_teams(process, order_id, traceback):
    send_exception(
        f"Order {process} unhandled exception!",
        f"An unhandled exception has been raised while performing {process} "
        f"of the order **{order_id}**:\n\n"
        f"```{traceback}```",
    )
