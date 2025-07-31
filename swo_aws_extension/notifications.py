import functools
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

import pymsteams
from django.conf import settings
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markdown_it import MarkdownIt
from mpt_extension_sdk.mpt_http.base import MPTClient
from mpt_extension_sdk.mpt_http.mpt import (
    get_rendered_template,
    notify,
)

NotifyCategories = Enum("NotifyCategories", settings.MPT_NOTIFY_CATEGORIES)

if TYPE_CHECKING:  # pragma: no cover
    from swo_aws_extension.flows.order import InitialAWSContext


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


def send_success(
    title: str,
    text: str,
    button: Button | None = None,
    facts: FactsSection | None = None,
) -> None:
    send_notification(
        f"\u2705 {title}",
        text,
        "#00FF00",
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


@dataclass
class MPTNotifier:  # TODO: Consider moving some of the functionality to SDK
    mpt_client: MPTClient

    def notify_re_order(self, order_context: type["InitialAWSContext"]) -> None:
        """
        Send an MPT notification to the customer according to the
        current order status.
        It embeds the current order template into the body.
        """
        template_context = {
            "order": order_context.order,
            "activation_template": md2html(
                get_rendered_template(self.mpt_client, order_context.order_id)
            ),
            "api_base_url": settings.MPT_API_BASE_URL,
            "portal_base_url": settings.MPT_PORTAL_BASE_URL,
        }
        buyer_name = order_context.buyer["name"]
        subject = f"Order status update {order_context.order_id} for {buyer_name}"
        if order_context.order_status == "Querying":
            subject = f"This order need your attention {order_context.order_id} for {buyer_name}"

        template = env.get_template("notification.html")
        rendered_template = template.render(template_context)

        self._notify(
            NotifyCategories.ORDERS.value,
            order_context.agreement["client"]["id"],
            order_context.buyer["id"],
            subject,
            rendered_template,
        )

    def _notify(
        self,
        notify_category: str,
        account_id: str,
        buyer_id: str,
        subject: str,
        rendered_template: str,
    ) -> None:
        """
        Sends a notification through the MPT API using a specified template and context.

        Raises:
        Exception
            Logs the exception if there is an issue during the notification process,
            including the category, subject, and the rendered message.
        """

        try:
            notify(
                self.mpt_client,
                notify_category,
                account_id,
                buyer_id,
                subject,
                rendered_template,
            )
            logger.debug(
                f"Sent MPT API notification:"
                f" Category: '{NotifyCategories.ORDERS.value}',"
                f" Account ID: '{account_id}',"
                f" Buyer ID: '{buyer_id}',"
                f" Subject: '{subject}',"
                f" Message: '{rendered_template}'"
            )
        except Exception:
            logger.exception(
                f"Cannot send MPT API notification:"
                f" Category: '{notify_category}',"
                f" Account ID: '{account_id}',"
                f" Buyer ID: '{buyer_id}',"
                f" Subject: '{subject}',"
                f" Message: '{rendered_template}'"
            )


def md2html(template):
    md = MarkdownIt("commonmark", {"breaks": True, "html": True})

    def custom_h1_renderer(tokens, idx, options, env):
        tokens[idx].attrSet("style", "line-height: 1.2em;")
        return md.renderer.renderToken(tokens, idx, options, env)

    md.renderer.rules["heading_open"] = custom_h1_renderer

    return md.render(template)


@functools.cache
def notify_unhandled_exception_in_teams(process, order_id, traceback):
    send_exception(
        f"Order {process} unhandled exception!",
        f"An unhandled exception has been raised while performing {process} "
        f"of the order **{order_id}**:\n\n"
        f"```{traceback}```",
    )
