import logging
from dataclasses import dataclass, field
from typing import Any

from swo_aws_extension.airtable.models import AccountMigrationFields
from swo_aws_extension.swo.notifications.teams import TeamsNotificationManager

logger = logging.getLogger(__name__)

NOTIFICATION_TITLE = "Synchronize AWS migration orders"
CLEARED_VALUE = "cleared"


def describe_row_changes(row_changes: dict[str, Any]) -> list[str]:
    """Describe the Airtable columns a row update touches, using the table column names."""
    descriptions = []
    for field_name, field_value in row_changes.items():
        column_name = AccountMigrationFields[field_name.upper()].value
        column_value = field_value or CLEARED_VALUE
        descriptions.append(f"{column_name}: {column_value}")
    return descriptions


@dataclass
class SyncReport:
    """
    Changes and errors of a synchronization run, reported to Teams at the end.

    The report is only sent when the run changed something or hit an error: a run where every
    row was already up to date is logged but does not notify. Changes are listed per order so
    the message tells what happened to each migration row.
    """

    dry_run: bool
    total_rows: int = 0
    updated_rows: list[str] = field(default_factory=list)
    failed_rows: dict[str, str] = field(default_factory=dict)
    created_tickets: list[str] = field(default_factory=list)
    started_onboardings: list[str] = field(default_factory=list)
    changes: dict[str, list[str]] = field(default_factory=dict)

    @property
    def has_changes(self) -> bool:
        """Whether the run changed a row, created a ticket or onboarding, or failed."""
        return bool(self.changes or self.failed_rows)

    def add_change(self, order_id: str, change: str) -> None:
        """Record something the run did to the row of the given order."""
        self.changes.setdefault(order_id, []).append(change)

    def add_row_changes(self, order_id: str, row_changes: dict[str, Any]) -> None:
        """Record the Airtable columns the run updates on the row of the given order."""
        for change in describe_row_changes(row_changes):
            self.add_change(order_id, change)

    def add_created_ticket(self, order_id: str, ticket_id: str) -> None:
        """Record the MCoE billing transfer start ticket created for the order."""
        self.created_tickets.append(order_id)
        self.add_change(order_id, f"Billing transfer start ticket {ticket_id} created")

    def add_started_onboarding(self, order_id: str, execution_arn: str) -> None:
        """Record the services onboarding launched for the order."""
        self.started_onboardings.append(order_id)
        self.add_change(order_id, f"Services onboarding started ({execution_arn})")

    def add_failed_row(self, order_id: str, message: str) -> None:
        """Report a row error, counting the row once and keeping its last error message."""
        self.failed_rows[order_id] = message

    def send(self) -> None:
        """Log the run summary and send it to Teams when something changed or failed."""
        summary = build_summary(self)
        if not self.has_changes:
            logger.info("%s Nothing to report.", summary)
            return
        logger.info(summary)
        sections = (summary, build_changes_section(self), build_errors_section(self))
        text = "\n\n".join(section for section in sections if section)
        if self.failed_rows:
            TeamsNotificationManager().send_warning(NOTIFICATION_TITLE, text)
            return
        TeamsNotificationManager().send_success(NOTIFICATION_TITLE, text)


def build_summary(report: SyncReport) -> str:
    """Build the one-line counters of the run."""
    summary = (
        f"Rows checked: {report.total_rows}. Rows updated: {len(report.updated_rows)}. "
        f"Tickets created: {len(report.created_tickets)}. "
        f"Onboardings started: {len(report.started_onboardings)}. "
        f"Rows with errors: {len(report.failed_rows)}."
    )
    return f"Dry run. {summary}" if report.dry_run else summary


def build_changes_section(report: SyncReport) -> str:
    """Build the per-order list of changes, or an empty string when nothing changed."""
    if not report.changes:
        return ""
    title = "Changes (dry run, not applied):" if report.dry_run else "Changes:"
    lines = [title]
    for order_id, order_changes in report.changes.items():
        order_summary = "; ".join(order_changes)
        lines.append(f"- {order_id}: {order_summary}")
    return "\n".join(lines)


def build_errors_section(report: SyncReport) -> str:
    """Build the per-order list of errors, or an empty string when no row failed."""
    if not report.failed_rows:
        return ""
    lines = ["Errors:"]
    for order_id, message in report.failed_rows.items():
        lines.append(f"- {order_id}: {message}")
    return "\n".join(lines)
