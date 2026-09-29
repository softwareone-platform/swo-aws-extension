import datetime as dt
import logging
from typing import Any

from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.airtable.account_migration_table import AwsAccountMigrationTable
from swo_aws_extension.airtable.models import AccountMigrationRecord, AccountMigrationStatus
from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.config import Config
from swo_aws_extension.constants import (
    DeploymentStatusEnum,
    MptOrderStatus,
    ResponsibilityTransferStatus,
)
from swo_aws_extension.flows.jobs.migration_billing_transfer_ticket import (
    create_ticket,
    get_stored_ticket_id,
    store_ticket_id,
)
from swo_aws_extension.flows.jobs.migration_services_onboarding import (
    get_onboarding_status,
    get_stored_execution_arn,
    start_onboarding,
    store_execution_arn,
)
from swo_aws_extension.flows.jobs.migration_sync_report import SyncReport
from swo_aws_extension.parameters import get_responsibility_transfer_id
from swo_aws_extension.swo.cloud_orchestrator.errors import CloudOrchestratorError
from swo_aws_extension.swo.crm_service.errors import CRMError
from swo_aws_extension.swo.mpt.order import get_orders_by_ids

logger = logging.getLogger(__name__)

ORDERS_QUERY_SELECT = (
    "select=audit,error,statusNotes,parameters,authorization.externalIds,"
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
    """
    Return the reason a failed order carries, or a generic message when it has none.

    The status notes hold the message the Marketplace shows for the failure (for example the
    vendor error that failed the order); the error field is the fallback for older orders.
    """
    for field_name in ("statusNotes", "error"):
        detail = order.get(field_name) or {}
        if isinstance(detail, dict) and detail.get("message"):
            return str(detail["message"])
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


class MigrationOrdersSyncProcessor:  # noqa: WPS214
    """
    Mirror the Marketplace migration orders into the AWS Account Migration Airtable table.

    The job runs daily over the rows still in progress. For every row it copies the order
    status and, depending on it, sets the customer acceptance date (migration in progress),
    the completion date (completed) or the error detail (failed). Once the billing transfer
    invitation of the order is accepted, the effective start date of the transfer is stored.
    When a completed row has a start date on or before the run date, the job creates the
    ServiceNow ticket that tells the MCoE team the billing transfer is active and stores its
    id in the crmMigrationTicketId parameter of the agreement; it then launches the services
    onboarding in Cloud Orchestrator, as the OnboardServices fulfillment step does, stores
    the execution ARN in the executionArn parameter of the agreement and checks the execution
    status. The row moves to Services onboarded only once the execution succeeded; while it
    is pending or running the row stays Completed and is checked again on the next run. A
    row whose ticket, onboarding or status check fails keeps the Completed status with the
    error detail and is retried on the next run; a ticket id or execution ARN already stored
    in the agreement is never created again. Every row is saved at most once.
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
            except Exception as error:
                logger.exception(
                    "%s - Error synchronizing migration row for MPA %s",
                    record.mpt_order_id,
                    record.masterpayer,
                )
                self.report.add_failed_row(record.mpt_order_id, f"Unexpected error: {error}")
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
            self.report.add_failed_row(
                str(order_id), f"Billing transfer {transfer_id} details not available: {error}"
            )
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
        """Create the MCoE ticket, onboard the services and mark the row once both are done."""
        if not self._ensure_billing_transfer_start_ticket(record, order, changes):
            return
        if not self._are_services_onboarded(record, order, changes):
            return
        changes["migration_status"] = AccountMigrationStatus.SERVICES_ONBOARDED
        changes["error"] = ""

    def _ensure_billing_transfer_start_ticket(
        self,
        record: AccountMigrationRecord,
        order: dict[str, Any],
        changes: dict[str, Any],
    ) -> bool:
        """Return whether the MCoE ticket exists, creating it when the agreement has none."""
        ticket_id = get_stored_ticket_id(order)
        if ticket_id:
            logger.info(
                "%s - Billing transfer start ticket %s already created, skipping creation",
                record.mpt_order_id,
                ticket_id,
            )
            return True
        return self._create_billing_transfer_start_ticket(record, order, changes)

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
            self._fail_row(record, changes, f"Billing transfer start ticket not created: {error}")
            return False
        self.report.add_created_ticket(order_id, ticket_id)
        if not store_ticket_id(self.mpt_client, order, ticket_id):
            self.report.add_failed_row(
                order_id, f"Ticket {ticket_id} created but not stored in the agreement"
            )
        return True

    def _are_services_onboarded(
        self,
        record: AccountMigrationRecord,
        order: dict[str, Any],
        changes: dict[str, Any],
    ) -> bool:
        """Launch the services onboarding once and return whether it has succeeded."""
        execution_arn = get_stored_execution_arn(order)
        if execution_arn:
            logger.info(
                "%s - Services onboarding already started with execution ARN %s",
                record.mpt_order_id,
                execution_arn,
            )
        else:
            execution_arn = self._start_services_onboarding(record, order, changes)
            if not execution_arn:
                return False
        return self._is_onboarding_succeeded(record, order, changes, execution_arn)

    def _start_services_onboarding(
        self,
        record: AccountMigrationRecord,
        order: dict[str, Any],
        changes: dict[str, Any],
    ) -> str:
        """
        Launch the onboarding, store its execution ARN in the agreement and return it.

        Returns an empty ARN when the onboarding could not be started or its ARN could not
        be stored, so the row is not checked nor onboarded in this run.
        """
        order_id = record.mpt_order_id
        logger.info("%s - Launching the services onboarding in Cloud Orchestrator", order_id)
        if self.dry_run:
            logger.info("%s - Dry run mode - skipping services onboarding", order_id)
            return ""
        try:
            execution_arn = start_onboarding(self.config, order)
        except CloudOrchestratorError as error:
            self._fail_row(record, changes, f"Services onboarding not started: {error}")
            return ""
        if not execution_arn:
            self._fail_row(record, changes, "Services onboarding started without an execution ARN")
            return ""
        logger.info(
            "%s - Services onboarding started with execution ARN %s", order_id, execution_arn
        )
        self.report.add_started_onboarding(order_id, execution_arn)
        if not store_execution_arn(self.mpt_client, order, execution_arn):
            # Without the stored ARN the next run would onboard again: stop here and keep
            # the ARN in the row error so an operator can store it in the agreement.
            self._fail_row(
                record,
                changes,
                f"Services onboarding started but execution ARN {execution_arn} was not "
                f"stored in the agreement. Store it in executionArn before the next run.",
            )
            return ""
        return execution_arn

    def _is_onboarding_succeeded(
        self,
        record: AccountMigrationRecord,
        order: dict[str, Any],
        changes: dict[str, Any],
        execution_arn: str,
    ) -> bool:
        """Check the onboarding execution and return whether it succeeded."""
        order_id = record.mpt_order_id
        try:
            status = get_onboarding_status(self.config, order, execution_arn)
        except CloudOrchestratorError as error:
            self._fail_row(record, changes, f"Services onboarding status not available: {error}")
            return False
        if status == DeploymentStatusEnum.SUCCEEDED:
            logger.info("%s - Services onboarding succeeded", order_id)
            return True
        if status == DeploymentStatusEnum.FAILED:
            self._fail_row(
                record,
                changes,
                f"Services onboarding failed in Cloud Orchestrator (execution {execution_arn})",
            )
            return False
        logger.info(
            "%s - Services onboarding status is %s, checking again on the next run",
            order_id,
            status or "unknown",
        )
        return False

    def _fail_row(
        self, record: AccountMigrationRecord, changes: dict[str, Any], message: str
    ) -> None:
        """Log the row error, keep it in the row and report it in the run summary."""
        logger.warning("%s - Error - %s", record.mpt_order_id, message)
        self.report.add_failed_row(record.mpt_order_id, message)
        changes["error"] = message

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
        self.report.add_row_changes(order_id, effective)
        if self.dry_run:
            logger.info("%s - Dry run mode - skipping Airtable update", order_id)
            return
        for field_name, field_value in effective.items():
            setattr(record, field_name, field_value)
        self.migration_table.save(record)
        self.report.updated_rows.append(order_id)
