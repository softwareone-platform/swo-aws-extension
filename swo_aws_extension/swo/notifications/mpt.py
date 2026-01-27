import datetime as dt
import logging
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from django.conf import settings
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markdown_it import MarkdownIt
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import get_rendered_template, notify

NotifyCategories = Enum("NotifyCategories", settings.MPT_NOTIFY_CATEGORIES)
if TYPE_CHECKING:
    from swo_aws_extension.flows.order import InitialAWSContext

logger = logging.getLogger(__name__)


def dateformat(date_string):
    """Formats date for notification format."""
    return dt.datetime.fromisoformat(date_string).strftime("%-d %B %Y") if date_string else ""


env = Environment(
    loader=FileSystemLoader(Path(__file__).resolve().parent / "templates"),
    autoescape=select_autoescape(),
)

env.filters["dateformat"] = dateformat


class MPTNotificationManager:
    """Notification manager used by business logic to send notifications through MPT API."""

    _notify_categories = NotifyCategories.ORDERS.value

    def __init__(self, client: MPTClient) -> None:
        self.client = client

    def send_notification(self, order_context: "InitialAWSContext") -> None:
        """Sends notification through MPT API based on order context."""
        template_context = {
            "order": order_context.order,
            "activation_template": self._md2html(
                get_rendered_template(self.client, order_context.order_id)
            ),
            "api_base_url": settings.MPT_API_BASE_URL,
            "portal_base_url": settings.MPT_PORTAL_BASE_URL,
        }

        buyer_name = order_context.buyer["name"]
        subject = f"Order status update {order_context.order_id} for {buyer_name}"

        if order_context.order_status == "Querying":
            subject = f"This order need your attention {order_context.order_id} for {buyer_name}"

        self._notify(
            order_context.agreement["client"]["id"],
            order_context.buyer["id"],
            subject,
            "notification",
            template_context,
        )

    def _notify(
        self,
        account_id: str,
        buyer_id: str,
        subject: str,
        template_name: str,
        context: dict,
    ) -> None:
        template = env.get_template(f"{template_name}.html")
        rendered_template = template.render(context)

        try:
            notify(
                self.client,
                self._notify_categories,
                account_id,
                buyer_id,
                subject,
                rendered_template,
            )
        except Exception:
            logger.exception(
                "Cannot send MPT API notification: Category: '%s', Account ID: '%s',"
                " Buyer ID: '%s', Subject: '%s', Message: '%s'",
                self._notify_categories,
                account_id,
                buyer_id,
                subject,
                rendered_template,
            )

    def _md2html(self, template):
        md = MarkdownIt("commonmark", {"breaks": True, "html": True})

        def custom_h1_renderer(tokens, idx, options, env):  # noqa: WPS430
            tokens[idx].attrSet("style", "line-height: 1.2em;")
            return md.renderer.renderToken(tokens, idx, options, env)

        md.renderer.rules["heading_open"] = custom_h1_renderer

        return md.render(template)
