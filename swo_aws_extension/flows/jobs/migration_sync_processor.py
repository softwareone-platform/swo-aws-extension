import datetime as dt
import logging
from dataclasses import dataclass, field
from typing import Any

from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.airtable.account_migration_table import AwsAccountMigrationTable
from swo_aws_extension.airtable.models import AccountMigrationRecord, AccountMigrationStatus
from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.config import Config
from swo_aws_extension.constants import MptOrderStatus, ResponsibilityTransferStatus
from swo_aws_extension.flows.jobs.migration_billing_transfer_ticket import (
    create_ticket,
    get_stored_ticket_id,
    store_ticket_id,
)
from swo_aws_extension.parameters import get_responsibility_transfer_id
from swo_aws_extension.swo.crm_service.errors import CRMError
from swo_aws_extension.swo.mpt.order import get_orders_by_ids
from swo_aws_extension.swo.notifications.teams import TeamsNotificationManager

logger = logging.getLogger(__name__)

NOTIFICATION_TITLE = "Synchronize AWS migration orders"
ORDERS_QUERY_SELECT = (
    "select=audit,error,parameters,authorization.externalIds,"
    "agreement,agreement.parameters,buyer,seller"
)

# Airtable rows the daily job keeps revisiting: rows whose Marketplace order can still change,
# and completed rows waiting for their billing transfer to become effective. Rows without an
# order, or already in a terminal migration status, are left untouched.
SYNCABLE_MIGRATION_STATUSES = (
    AccountMigrationStatus.PENDING_NOTIFY_CUSTOMER,
    AccountMigrationStatus.MIGRATION_IN_PROGRESS,
    AccountMigrationStatus.COMPLETED,
)

# Order statuses that mean the customer has accepted the quoted order (moved it to processing).
ACCEPTED_ORDER_STATUSES = frozenset((
    MptOrderStatus.PROCESSING,
    MptOrderStatus.QUERYING,
    MptOrderStatus.COMPLETED,
))

IN_PROGRESS_ORDER_STATUSES = frozenset((MptOrderStatus.PROCESSING, MptOrderStatus.QUERYING))

FAILED_ORDER_STATUSES = frozenset((MptOrderStatus.FAILED, MptOrderStatus.DELETED))


def get_audit_date(order: dict[str, Any], status: MptOrderStatus) -> str | None:
    """
    Return the ISO date (YYYY-MM-DD) when the order entered the given status.

    The audit entry of the status is used when present; otherwise the last update date of the
    order is used, since the status change is the last thing that happened to it.
    """
    audit = order.get("audit") or {}
    entry = audit.get(status.value.lower()) or audit.get("updated")
    return get_iso_date((entry or {}).get("at"))


def get_iso_date(timestamp: dt.datetime | str | None) -> str | None:
    """Return the ISO date (YYYY-MM-DD) of a datetime or ISO timestamp, or None when empty."""
    if not timestamp:
        return None
    if isinstance(timestamp, str):
        timestamp = dt.datetime.fromisoformat(timestamp)
    return timestamp.date().isoformat()


def get_pma_account_id(order: dict[str, Any]) -> str | None:
    """Return the Program Management Account of the order authorization, if any."""
    authorization = order.get("authorization") or {}
    return authorization.get("externalIds", {}).get("operations")


def get_order_error(order: dict[str, Any]) -> str:
    """Return the error detail of a failed order, or a generic message when it carries none."""
    error = order.get("error") or {}
    if isinstance(error, dict) and error.get("message"):
        return str(error["message"])
    return f"Order {order.get('id')} is {order.get('status')}"


def is_billing_transfer_effective(
    record: AccountMigrationRecord, changes: dict[str, Any], run_date: dt.date
) -> bool:
    """
    Return whether the row, once the changes apply, is completed with an effective transfer.

    The billing transfer is effective when its start date is on or before the run date. An
    invalid start date is logged and treated as not effective, so it never stops the run.
    """
    status = changes.get("migration_status", record.migration_status)
    start_date = changes.get("billing_transfer_start_date") or record.billing_transfer_start_date
    if status != AccountMigrationStatus.COMPLETED or not start_date:
        return False
    try:
        return dt.date.fromisoformat(start_date) <= run_date
    except ValueError:
        logger.warning(
            "%s - Invalid billing transfer start date %s for MPA %s",
            record.mpt_order_id,
            start_date,
            record.masterpayer,
        )
        return False


@dataclass
class SyncReport:
    """Counters of a synchronization run, reported to Teams at the end."""

    dry_run: bool
    total_rows: int = 0
    updated_rows: list[str] = field(default_factory=list)
    failed_rows: list[str] = field(default_factory=list)
    created_tickets: list[str] = field(default_factory=list)

    def send(self) -> None:
        """Log the run summary and send it to Teams, as a warning when a row failed."""
        summary = (
            f"Rows checked: {self.total_rows}. Rows updated: {len(self.updated_rows)}. "
            f"Tickets created: {len(self.created_tickets)}. "
            f"Rows with errors: {len(self.failed_rows)}."
        )
        if self.dry_run:
            summary = f"Dry run. {summary}"
        logger.info(summary)
        if self.failed_rows:
            failed_orders = ", ".join(self.failed_rows)
            TeamsNotificationManager().send_warning(
                NOTIFICATION_TITLE, f"{summary}\n\nOrders with errors: {failed_orders}"
            )
            return
        TeamsNotificationManager().send_success(NOTIFICATION_TITLE, summary)


class MigrationOrdersSyncProcessor:  # noqa: WPS214
    """
    Mirror the Marketplace migration orders into the AWS Account Migration Airtable table.

    The job runs daily over the rows still in progress. For every row it copies the order
    status and, depending on it, sets the customer acceptance date (migration in progress),
    the completion date (completed) or the error detail (failed). Once the billing transfer
    invitation of the order is accepted, the effective start date of the transfer is stored.
    When a completed row has a start date on or before the run date, the job creates the
    ServiceNow ticket that tells the MCoE team the billing transfer is active, stores its id
    in the crmMigrationTicketId parameter of the agreement and moves the row to Services
    onboarded; migrated customers keep their existing CCO and ERP project, so no services
    onboarding call is made. A row whose ticket fails keeps the Completed status with the
    error detail and is retried on the next run, and a ticket already stored in the agreement
    is never created again. Every row is saved at most once.
    """

    def __init__(
        self,
        mpt_client: MPTClient,
        config: Config,
        run_date: dt.date,
        *,
        dry_run: bool = False,
    ) -> None:
        self.mpt_client = mpt_client
        self.config = config
        self.run_date = run_date
        self.dry_run = dry_run
        self.migration_table = AwsAccountMigrationTable()
        self.report = SyncReport(dry_run=dry_run)
        self._aws_clients: dict[str, AWSClient] = {}

    def sync(self) -> None:
        """Synchronize the Airtable rows with their Marketplace orders and report to Teams."""
        records = self._get_records_to_sync()
        self.report.total_rows = len(records)
        logger.info("Synchronizing %s migration rows with their orders", len(records))
        orders = get_orders_by_ids(
            self.mpt_client, [record.mpt_order_id for record in records], ORDERS_QUERY_SELECT
        )
        for record in records:
            try:
                self._sync_record(record, orders.get(record.mpt_order_id))
            except Exception:
                logger.exception(
                    "%s - Error synchronizing migration row for MPA %s",
                    record.mpt_order_id,
                    record.masterpayer,
                )
                self.report.failed_rows.append(record.mpt_order_id)
        self.report.send()

    def _get_records_to_sync(self) -> list[AccountMigrationRecord]:
        records = self.migration_table.get_by_statuses(SYNCABLE_MIGRATION_STATUSES)
        with_order = [record for record in records if record.mpt_order_id]
        skipped = len(records) - len(with_order)
        if skipped:
            logger.info("Skipping %s migration rows without a Marketplace order id", skipped)
        return with_order

    def _sync_record(self, record: AccountMigrationRecord, order: dict[str, Any] | None) -> None:
        order_id = record.mpt_order_id
        if order is None:
            logger.warning(
                "%s - Order not found in the marketplace, marking row as failed", order_id
            )
            self._save(
                record,
                mpt_order_status=MptOrderStatus.FAILED.value,
                migration_status=AccountMigrationStatus.FAILED,
                error=f"Order {order_id} not found in the marketplace",
            )
            return

        changes = self._get_status_changes(order)
        if order.get("status") in ACCEPTED_ORDER_STATUSES:
            changes.update(self._get_acceptance_changes(record, order))
        if is_billing_transfer_effective(record, changes, self.run_date):
            self._start_billing_transfer(record, order, changes)
        self._save(record, **changes)

    def _get_status_changes(self, order: dict[str, Any]) -> dict[str, Any]:
        """Return the row changes driven by the order status alone."""
        order_status = order.get("status")
        changes: dict[str, Any] = {"mpt_order_status": order_status}
        if order_status in IN_PROGRESS_ORDER_STATUSES:
            changes["migration_status"] = AccountMigrationStatus.MIGRATION_IN_PROGRESS
        elif order_status == MptOrderStatus.COMPLETED:
            changes["migration_status"] = AccountMigrationStatus.COMPLETED
            changes["migration_completed_date"] = get_audit_date(order, MptOrderStatus.COMPLETED)
        elif order_status in FAILED_ORDER_STATUSES:
            changes["mpt_order_status"] = MptOrderStatus.FAILED.value
            changes["migration_status"] = AccountMigrationStatus.FAILED
            changes["error"] = get_order_error(order)
        return changes

    def _get_acceptance_changes(
        self, record: AccountMigrationRecord, order: dict[str, Any]
    ) -> dict[str, Any]:
        """Return the dates set once the customer accepted the order, when still missing."""
        changes: dict[str, Any] = {}
        if not record.customer_accepted_date:
            changes["customer_accepted_date"] = get_audit_date(order, MptOrderStatus.PROCESSING)
        if not record.billing_transfer_start_date:
            changes["billing_transfer_start_date"] = self._get_billing_transfer_start_date(order)
        return changes

    def _get_billing_transfer_start_date(self, order: dict[str, Any]) -> str | None:
        """Return the effective start date of the accepted billing transfer, if any."""
        order_id = order.get("id")
        transfer_id = get_responsibility_transfer_id(order)
        pma_account_id = get_pma_account_id(order)
        if not transfer_id or not pma_account_id:
            return None
        try:
            transfer = self._get_aws_client(pma_account_id).get_responsibility_transfer_details(
                transfer_id=transfer_id
            )
        except AWSError as error:
            logger.warning(
                "%s - Error - Failed to get billing transfer %s details: %s",
                order_id,
                transfer_id,
                error,
            )
            self.report.failed_rows.append(str(order_id))
            return None
        transfer_details = transfer.get("ResponsibilityTransfer", {})
        if transfer_details.get("Status") != ResponsibilityTransferStatus.ACCEPTED:
            logger.info(
                "%s - Billing transfer %s not accepted yet (%s)",
                order_id,
                transfer_id,
                transfer_details.get("Status"),
            )
            return None
        return get_iso_date(transfer_details.get("StartTimestamp"))

    def _get_aws_client(self, pma_account_id: str) -> AWSClient:
        if pma_account_id not in self._aws_clients:
            self._aws_clients[pma_account_id] = AWSClient(
                self.config, pma_account_id, self.config.management_role_name
            )
        return self._aws_clients[pma_account_id]

    def _start_billing_transfer(
        self,
        record: AccountMigrationRecord,
        order: dict[str, Any],
        changes: dict[str, Any],
    ) -> None:
        """Create the MCoE ticket of the effective transfer and mark the row Services onboarded."""
        order_id = record.mpt_order_id
        ticket_id = get_stored_ticket_id(order)
        if ticket_id:
            logger.info(
                "%s - Billing transfer start ticket %s already created, skipping creation",
                order_id,
                ticket_id,
            )
        elif not self._create_billing_transfer_start_ticket(record, order, changes):
            return
        changes["migration_status"] = AccountMigrationStatus.SERVICES_ONBOARDED
        changes["error"] = ""

    def _create_billing_transfer_start_ticket(
        self,
        record: AccountMigrationRecord,
        order: dict[str, Any],
        changes: dict[str, Any],
    ) -> bool:
        """Create the MCoE ticket and store its id; return whether the row can be onboarded."""
        order_id = record.mpt_order_id
        start_date = (
            changes.get("billing_transfer_start_date") or record.billing_transfer_start_date
        )
        logger.info("%s - Creating the billing transfer start ticket for MCoE", order_id)
        if self.dry_run:
            logger.info("%s - Dry run mode - skipping ticket creation", order_id)
            return True
        try:
            ticket_id = create_ticket(record, order, start_date)
        except CRMError as error:
            logger.warning(
                "%s - Error - Failed to create the billing transfer start ticket: %s",
                order_id,
                error,
            )
            self.report.failed_rows.append(order_id)
            changes["error"] = str(error)
            return False
        self.report.created_tickets.append(order_id)
        if not store_ticket_id(self.mpt_client, order, ticket_id):
            self.report.failed_rows.append(order_id)
        return True

    def _save(self, record: AccountMigrationRecord, **changes: Any) -> None:
        order_id = record.mpt_order_id
        effective = {
            field_name: field_value
            for field_name, field_value in changes.items()
            if field_value is not None and (getattr(record, field_name) or "") != field_value
        }
        if not effective:
            logger.info("%s - Migration row already up to date", order_id)
            return
        logger.info("%s - Updating migration row: %s", order_id, effective)
        if self.dry_run:
            logger.info("%s - Dry run mode - skipping Airtable update", order_id)
            return
        for field_name, field_value in effective.items():
            setattr(record, field_name, field_value)
        self.migration_table.save(record)
        self.report.updated_rows.append(order_id)
