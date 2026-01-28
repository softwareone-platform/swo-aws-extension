import functools
import logging
from dataclasses import dataclass

import pymsteams
from django.conf import settings

logger = logging.getLogger(__name__)


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

    def _send_notification(  # noqa: WPS213
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
