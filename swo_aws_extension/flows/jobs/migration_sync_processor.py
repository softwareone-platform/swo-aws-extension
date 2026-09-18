import datetime as dt
import logging
from itertools import batched
from typing import Any

from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.airtable.account_migration_table import AwsAccountMigrationTable
from swo_aws_extension.airtable.models import AccountMigrationRecord, AccountMigrationStatus
from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.config import Config
from swo_aws_extension.constants import MptOrderStatus, ResponsibilityTransferStatus
from swo_aws_extension.parameters import get_responsibility_transfer_id
from swo_aws_extension.swo.mpt.order import get_orders_by_query
from swo_aws_extension.swo.notifications.teams import TeamsNotificationManager
from swo_aws_extension.swo.rql.query_builder import RQLQuery

logger = logging.getLogger(__name__)

NOTIFICATION_TITLE = "Synchronize AWS migration orders"
ORDERS_QUERY_BATCH_SIZE = 50
ORDERS_QUERY_SELECT = "select=audit,error,parameters,authorization.externalIds"

# Airtable rows whose Marketplace order can still change. Rows without an order, or already
# in a terminal migration status, are left untouched by the synchronization.
SYNCABLE_MIGRATION_STATUSES = (
    AccountMigrationStatus.PENDING_NOTIFY_CUSTOMER,
    AccountMigrationStatus.MIGRATION_IN_PROGRESS,
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


class MigrationOrdersSyncProcessor:  # noqa: WPS214
    """
    Mirror the Marketplace migration orders into the AWS Account Migration Airtable table.

    For every row still waiting on its order, the job copies the order status and, depending
    on it, sets the customer acceptance date (migration in progress), the completion date
    (completed) or the error detail (failed). Once the billing transfer invitation of the order
    is accepted, the effective start date of the transfer is stored so the day-1 logic can
    pick the row up. Rows in a terminal status are not touched.
    """

    def __init__(self, mpt_client: MPTClient, config: Config, *, dry_run: bool = False) -> None:
        self.mpt_client = mpt_client
        self.config = config
        self.dry_run = dry_run
        self.migration_table = AwsAccountMigrationTable()
        self.updated_rows: list[str] = []
        self.failed_rows: list[str] = []
        self._aws_clients: dict[str, AWSClient] = {}

    def sync(self) -> None:
        """Synchronize the Airtable rows with their Marketplace orders and report to Teams."""
        records = self._get_records_to_sync()
        logger.info("Synchronizing %s migration rows with their orders", len(records))
        orders = self._get_orders_by_id([record.mpt_order_id for record in records])
        for record in records:
            try:
                self._sync_record(record, orders.get(record.mpt_order_id))
            except Exception:
                logger.exception(
                    "%s - Error synchronizing migration row for MPA %s",
                    record.mpt_order_id,
                    record.masterpayer,
                )
                self.failed_rows.append(record.mpt_order_id)
        self._send_report(len(records))

    def _get_records_to_sync(self) -> list[AccountMigrationRecord]:
        records = []
        for status in SYNCABLE_MIGRATION_STATUSES:
            records.extend(self.migration_table.get_by_status(status))
        with_order = [record for record in records if record.mpt_order_id]
        skipped = len(records) - len(with_order)
        if skipped:
            logger.info("Skipping %s migration rows without a Marketplace order id", skipped)
        return with_order

    def _get_orders_by_id(self, order_ids: list[str]) -> dict[str, dict[str, Any]]:
        orders: dict[str, dict[str, Any]] = {}
        for order_ids_batch in batched(order_ids, ORDERS_QUERY_BATCH_SIZE):
            query = f"{RQLQuery(id__in=list(order_ids_batch))}&{ORDERS_QUERY_SELECT}"
            for order in get_orders_by_query(self.mpt_client, query, limit=ORDERS_QUERY_BATCH_SIZE):
                orders[order["id"]] = order
        return orders

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
            self.failed_rows.append(str(order_id))
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

    def _save(self, record: AccountMigrationRecord, **changes: Any) -> None:
        order_id = record.mpt_order_id
        effective = {
            field_name: field_value
            for field_name, field_value in changes.items()
            if field_value is not None and getattr(record, field_name) != field_value
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
        self.updated_rows.append(order_id)

    def _send_report(self, total_rows: int) -> None:
        summary = (
            f"Rows checked: {total_rows}. Rows updated: {len(self.updated_rows)}. "
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
