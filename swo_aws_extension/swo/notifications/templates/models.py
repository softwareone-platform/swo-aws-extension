"""Email Templates models."""

from dataclasses import dataclass


@dataclass(frozen=True)
class EmailNotificationTemplate:
    """Base dataclass for Email notification templates.

    Attributes:
        subject: The subject of the email notification.
        body: The body template string with placeholders for formatting.
    """

    subject: str
    body: str
