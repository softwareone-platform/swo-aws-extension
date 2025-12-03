import datetime as dt
import functools
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

import pymsteams
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


@dataclass
class Button:
    """MS Teams button."""

    label: str
    url: str


@dataclass
class FactsSection:
    """MS Teams facts section."""

    title: str
    data: dict  # noqa: WPS110


class TeamsNotificationManager:
    """Notification manager used by business logic to send notifications to MS Teams."""

    def send_warning(
        self,
        title: str,
        text: str,
        button: Button | None = None,
        facts: FactsSection | None = None,
    ) -> None:
        """Send a warning notification."""
        self._send_notification(
            f"\u2622 {title}",
            text,
            "#ffa500",
            button=button,
            facts=facts,
        )

    def send_success(
        self,
        title: str,
        text: str,
        button: Button | None = None,
        facts: FactsSection | None = None,
    ) -> None:
        """Send a success notification."""
        self._send_notification(
            f"\u2705 {title}",
            text,
            "#00FF00",
            button=button,
            facts=facts,
        )

    def send_error(
        self,
        title: str,
        text: str,
        button: Button | None = None,
        facts: FactsSection | None = None,
    ) -> None:
        """Send an error notification."""
        self._send_notification(
            f"\U0001f4a3 {title}",
            text,
            "#df3422",
            button=button,
            facts=facts,
        )

    def send_exception(
        self,
        title: str,
        text: str,
        button: Button | None = None,
        facts: FactsSection | None = None,
    ) -> None:
        """Send an exception notification."""
        self._send_notification(
            f"\U0001f525 {title}",
            text,
            "#541c2e",
            button=button,
            facts=facts,
        )

    @functools.cache  # noqa: B019
    def notify_one_time_error(self, title: str, message: str) -> None:
        """Send a one-time error notification once per (title, message) pair."""
        self.send_exception(title, message)

    def _send_notification(
        self,
        title: str,
        text: str,
        color: str,
        button: Button | None = None,
        facts: FactsSection | None = None,
    ) -> None:
        """Sends ms teams notification."""
        message = pymsteams.connectorcard(settings.EXTENSION_CONFIG["MSTEAMS_WEBHOOK_URL"])
        message.color(color)
        message.title(title)
        message.text(text)
        if button:
            message.addLinkButton(button.label, button.url)
        if facts:
            facts_section = pymsteams.cardsection()
            facts_section.title(facts.title)
            for key, facts_data in facts.data.items():
                facts_section.addFact(key, facts_data)
            message.addSection(facts_section)

        try:
            message.send()
        except pymsteams.TeamsWebhookException:
            logger.exception("Error sending notification to MSTeams!")


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

        def custom_h1_renderer(tokens, idx, options, env):
            tokens[idx].attrSet("style", "line-height: 1.2em;")
            return md.renderer.renderToken(tokens, idx, options, env)

        md.renderer.rules["heading_open"] = custom_h1_renderer

        return md.render(template)
