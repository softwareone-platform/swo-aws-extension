import enum
import functools
import logging
from dataclasses import dataclass

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT = 10


class Style(enum.Enum):
    """Adaptive Card container style and text color."""

    WARNING = ("warning", "Warning")
    SUCCESS = ("good", "Good")
    ATTENTION = ("attention", "Attention")

    def __init__(self, container: str, color: str) -> None:
        self.container = container
        self.color = color


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


@functools.cache
def notify_one_time_error(title: str, message: str) -> None:
    """Send a one-time error notification once per (title, message) pair."""
    TeamsNotificationManager().send_exception(title, message)


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
        self._send_notification(f"\u2622 {title}", text, Style.WARNING, button=button, facts=facts)

    def send_success(
        self,
        title: str,
        text: str,
        button: Button | None = None,
        facts: FactsSection | None = None,
    ) -> None:
        """Send a success notification."""
        self._send_notification(f"\u2705 {title}", text, Style.SUCCESS, button=button, facts=facts)

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
            Style.ATTENTION,
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
            Style.ATTENTION,
            button=button,
            facts=facts,
        )

    def _build_card(
        self,
        title: str,
        text: str,
        style: Style,
        button: Button | None,
        facts: FactsSection | None,
    ) -> dict:
        """Builds the Adaptive Card payload wrapped in the Workflows envelope."""
        body: list[dict] = [
            {
                "type": "Container",
                "style": style.container,
                "bleed": True,
                "items": [
                    {
                        "type": "TextBlock",
                        "text": title,
                        "weight": "Bolder",
                        "size": "Large",
                        "color": style.color,
                        "wrap": True,
                    },
                ],
            },
            {"type": "TextBlock", "text": text, "wrap": True},
        ]

        if facts:
            if facts.title:
                body.append(
                    {"type": "TextBlock", "text": facts.title, "weight": "Bolder", "wrap": True},
                )
            body.append(
                {
                    "type": "FactSet",
                    "facts": [
                        {"title": key, "value": fact_value}
                        for key, fact_value in facts.data.items()
                    ],
                },
            )

        card: dict = {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "msteams": {"width": "Full"},
            "body": body,
        }

        if button:
            card["actions"] = [
                {"type": "Action.OpenUrl", "title": button.label, "url": button.url},
            ]

        return {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": card,
                },
            ],
        }

    def _send_notification(
        self,
        title: str,
        text: str,
        style: Style,
        button: Button | None = None,
        facts: FactsSection | None = None,
    ) -> None:
        """Sends an Adaptive Card to the MS Teams Workflow webhook."""
        payload = self._build_card(title, text, style, button, facts)

        try:
            requests.post(
                settings.EXTENSION_CONFIG["MSTEAMS_WEBHOOK_URL"],
                json=payload,
                timeout=_REQUEST_TIMEOUT,
            ).raise_for_status()
        except requests.RequestException:
            logger.exception("Error sending notification to MSTeams!")
