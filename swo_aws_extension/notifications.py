import datetime as dt
import functools
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import pymsteams
from django.conf import settings
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markdown_it import MarkdownIt

NotifyCategories = Enum("NotifyCategories", settings.MPT_NOTIFY_CATEGORIES)


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


def send_notification(
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


def send_warning(
    title: str,
    text: str,
    button: Button | None = None,
    facts: FactsSection | None = None,
) -> None:
    """Sends ms teams warning notification."""
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
    """Sends ms teams success notifications."""
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
    """Sends ms teams error notifications."""
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
    """Sends ms teams exception notifications."""
    send_notification(
        f"\U0001f525 {title}",
        text,
        "#541c2e",
        button=button,
        facts=facts,
    )


def md2html(template):
    """Converts markdown to html."""
    md = MarkdownIt("commonmark", {"breaks": True, "html": True})

    def custom_h1_renderer(tokens, idx, options, env):
        tokens[idx].attrSet("style", "line-height: 1.2em;")
        return md.renderer.renderToken(tokens, idx, options, env)

    md.renderer.rules["heading_open"] = custom_h1_renderer

    return md.render(template)


@functools.cache
def notify_unhandled_exception_in_teams(process, order_id, traceback):
    """Sends unhandled exceptions to ms teams."""
    send_exception(
        f"Order {process} unhandled exception!",
        f"An unhandled exception has been raised while performing {process} "
        f"of the order **{order_id}**:\n\n"
        f"```{traceback}```",
    )
