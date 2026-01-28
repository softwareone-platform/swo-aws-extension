"""CRM Ticket Templates models."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CRMTicketTemplate:
    """Base dataclass for CRM ticket templates.

    Attributes:
        title: The title of the CRM ticket.
        additional_info: Additional information for the CRM ticket.
        summary: The summary template string with placeholders for formatting.
    """

    title: str
    additional_info: str
    summary: str
