import datetime as dt

import pytest

from swo_aws_extension.airtable.models import AccountMigrationRecord, AccountMigrationStatus
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.constants import (
    FulfillmentParametersEnum,
    MptOrderStatus,
    ResponsibilityTransferStatus,
)
from swo_aws_extension.flows.jobs.migration_sync_processor import (
    NOTIFICATION_TITLE,
    ORDERS_QUERY_BATCH_SIZE,
    ORDERS_QUERY_SELECT,
    MigrationOrdersSyncProcessor,
    get_audit_date,
    get_iso_date,
    get_order_error,
)

ORDER_ID = "ORD-0792-5000-2253-4210"
PROCESSING_AT = "2026-09-10T08:15:00.000Z"
COMPLETED_AT = "2026-09-17T16:40:00.000Z"
UPDATED_AT = "2026-09-18T09:00:00.000Z"
TRANSFER_ID = "rt-8lr3q6sn"
PMA_ACCOUNT_ID = "123456789012"
TRANSFER_START = dt.datetime.fromisoformat("2026-10-01T00:00:00+00:00")


@pytest.fixture
def mock_migration_table(mocker):
    mock_table = mocker.MagicMock()
    mock_table.get_by_status.return_value = []
    mocker.patch(
        "swo_aws_extension.flows.jobs.migration_sync_processor.AwsAccountMigrationTable",
        return_value=mock_table,
    )
    return mock_table


@pytest.fixture
def mock_get_orders(mocker):
    return mocker.patch(
        "swo_aws_extension.flows.jobs.migration_sync_processor.get_orders_by_query",
        return_value=[],
    )


@pytest.fixture
def mock_teams(mocker):
    return mocker.patch(
        "swo_aws_extension.flows.jobs.migration_sync_processor.TeamsNotificationManager"
    ).return_value


@pytest.fixture
def mock_aws_client(mocker):
    mock_client = mocker.MagicMock()
    mock_client.get_responsibility_transfer_details.return_value = {
        "ResponsibilityTransfer": {
            "Status": ResponsibilityTransferStatus.ACCEPTED,
            "StartTimestamp": TRANSFER_START,
        }
    }
    mocker.patch(
        "swo_aws_extension.flows.jobs.migration_sync_processor.AWSClient",
        return_value=mock_client,
    )
    return mock_client


@pytest.fixture
def migration_record_factory():
    def factory(**overrides):
        record_values = {
            "record_id": "rec123",
            "swo_seller": "SEL-1111-1111",
            "swo_buyer": "BUY-1111-1111",
            "masterpayer": "123456789012",
            "mpt_cco": "CCO-0001",
            "aws_account_email": "root@example.com",
            "aws_support_type": "resoldSupport",
            "technical_contact_name": "Jane Doe",
            "technical_contact_email": "jane.doe@example.com",
            "group": "Group A",
            "batch": "Batch 1",
            "migration_status": AccountMigrationStatus.PENDING_NOTIFY_CUSTOMER,
            "mpt_order_id": ORDER_ID,
            "mpt_order_status": MptOrderStatus.DRAFT.value,
        }
        record_values.update(overrides)
        return AccountMigrationRecord(**record_values)

    return factory


@pytest.fixture
def order_factory_sync():
    def factory(
        status=MptOrderStatus.PROCESSING.value,
        order_id=ORDER_ID,
        audit=None,
        error=None,
        transfer_id=TRANSFER_ID,
        pma_account_id=PMA_ACCOUNT_ID,
    ):
        if audit is None:
            audit = {
                "updated": {"at": UPDATED_AT},
                "processing": {"at": PROCESSING_AT},
                "completed": {"at": COMPLETED_AT},
            }
        return {
            "id": order_id,
            "status": status,
            "audit": audit,
            "error": error,
            "parameters": {
                "ordering": [],
                "fulfillment": [
                    {
                        "externalId": FulfillmentParametersEnum.RESPONSIBILITY_TRANSFER_ID.value,
                        "value": transfer_id,
                    }
                ],
            },
            "authorization": {"externalIds": {"operations": pma_account_id}},
        }

    return factory


@pytest.fixture
def processor(
    mpt_client, config, mock_migration_table, mock_get_orders, mock_teams, mock_aws_client
):
    return MigrationOrdersSyncProcessor(mpt_client, config)


def test_get_audit_date_uses_status_entry(order_factory_sync):
    order = order_factory_sync()

    result = get_audit_date(order, MptOrderStatus.PROCESSING)

    assert result == "2026-09-10"


def test_get_audit_date_falls_back_to_updated(order_factory_sync):
    order = order_factory_sync(audit={"updated": {"at": UPDATED_AT}})

    result = get_audit_date(order, MptOrderStatus.COMPLETED)

    assert result == "2026-09-18"


@pytest.mark.parametrize(
    ("timestamp", "expected"),
    [
        (TRANSFER_START, "2026-10-01"),
        ("2026-10-01T00:00:00+00:00", "2026-10-01"),
        (None, None),
    ],
)
def test_to_iso_date(timestamp, expected):
    result = get_iso_date(timestamp)

    assert result == expected


def test_get_audit_date_without_audit(order_factory_sync):
    order = order_factory_sync(audit={})

    result = get_audit_date(order, MptOrderStatus.COMPLETED)

    assert result is None


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        ({"id": "AWS001", "message": "Invitation declined"}, "Invitation declined"),
        ({}, f"Order {ORDER_ID} is Failed"),
        (None, f"Order {ORDER_ID} is Failed"),
    ],
)
def test_get_order_error(order_factory_sync, error, expected):
    order = order_factory_sync(status=MptOrderStatus.FAILED.value, error=error)

    result = get_order_error(order)

    assert result == expected


def test_sync_reads_pending_and_in_progress_rows(processor, mock_migration_table):
    processor.sync()  # act

    assert [call.args[0] for call in mock_migration_table.get_by_status.call_args_list] == [
        AccountMigrationStatus.PENDING_NOTIFY_CUSTOMER,
        AccountMigrationStatus.MIGRATION_IN_PROGRESS,
    ]


def test_sync_skips_rows_without_order_and_queries_nothing(
    processor, mock_migration_table, mock_get_orders, mock_teams, migration_record_factory
):
    mock_migration_table.get_by_status.side_effect = [
        [migration_record_factory(mpt_order_id=None)],
        [],
    ]

    processor.sync()  # act

    mock_get_orders.assert_not_called()
    mock_migration_table.save.assert_not_called()
    mock_teams.send_success.assert_called_once_with(
        NOTIFICATION_TITLE, "Rows checked: 0. Rows updated: 0. Rows with errors: 0."
    )


def test_sync_queries_orders_by_id_with_audit(
    processor, mock_migration_table, mock_get_orders, migration_record_factory, order_factory_sync
):
    mock_migration_table.get_by_status.side_effect = [
        [migration_record_factory(), migration_record_factory(mpt_order_id="ORD-2")],
        [],
    ]
    mock_get_orders.return_value = [order_factory_sync(), order_factory_sync(order_id="ORD-2")]

    processor.sync()  # act

    mock_get_orders.assert_called_once_with(
        processor.mpt_client,
        f"in(id,({ORDER_ID},ORD-2))&{ORDERS_QUERY_SELECT}",
        limit=ORDERS_QUERY_BATCH_SIZE,
    )


def test_sync_processing_order_sets_acceptance_and_in_progress(
    processor, mock_migration_table, mock_get_orders, migration_record_factory, order_factory_sync
):
    record = migration_record_factory()
    mock_migration_table.get_by_status.side_effect = [[record], []]
    mock_get_orders.return_value = [order_factory_sync(status=MptOrderStatus.PROCESSING.value)]

    processor.sync()  # act

    mock_migration_table.save.assert_called_once_with(record)
    assert record.mpt_order_status == MptOrderStatus.PROCESSING.value
    assert record.customer_accepted_date == "2026-09-10"
    assert record.migration_status == AccountMigrationStatus.MIGRATION_IN_PROGRESS
    assert record.billing_transfer_start_date == "2026-10-01"
    assert record.migration_completed_date is None


def test_sync_accepted_transfer_sets_start_date_from_aws(
    mocker,
    processor,
    mock_migration_table,
    mock_get_orders,
    mock_aws_client,
    migration_record_factory,
    order_factory_sync,
    config,
):
    aws_client_class = mocker.patch(
        "swo_aws_extension.flows.jobs.migration_sync_processor.AWSClient",
        return_value=mock_aws_client,
    )
    record = migration_record_factory()
    mock_migration_table.get_by_status.side_effect = [[record], []]
    mock_get_orders.return_value = [order_factory_sync()]

    processor.sync()  # act

    aws_client_class.assert_called_once_with(config, PMA_ACCOUNT_ID, config.management_role_name)
    mock_aws_client.get_responsibility_transfer_details.assert_called_once_with(
        transfer_id=TRANSFER_ID
    )
    assert record.billing_transfer_start_date == "2026-10-01"


def test_sync_pending_transfer_leaves_start_date_empty(
    processor,
    mock_migration_table,
    mock_get_orders,
    mock_aws_client,
    migration_record_factory,
    order_factory_sync,
):
    mock_aws_client.get_responsibility_transfer_details.return_value = {
        "ResponsibilityTransfer": {"Status": ResponsibilityTransferStatus.REQUESTED}
    }
    record = migration_record_factory()
    mock_migration_table.get_by_status.side_effect = [[record], []]
    mock_get_orders.return_value = [order_factory_sync()]

    processor.sync()  # act

    assert record.billing_transfer_start_date is None
    assert record.migration_status == AccountMigrationStatus.MIGRATION_IN_PROGRESS


def test_sync_skips_aws_when_order_has_no_transfer_id(
    processor,
    mock_migration_table,
    mock_get_orders,
    mock_aws_client,
    migration_record_factory,
    order_factory_sync,
):
    record = migration_record_factory()
    mock_migration_table.get_by_status.side_effect = [[record], []]
    mock_get_orders.return_value = [order_factory_sync(transfer_id="")]

    processor.sync()  # act

    mock_aws_client.get_responsibility_transfer_details.assert_not_called()
    assert record.billing_transfer_start_date is None


def test_sync_skips_aws_when_start_date_already_set(
    processor,
    mock_migration_table,
    mock_get_orders,
    mock_aws_client,
    migration_record_factory,
    order_factory_sync,
):
    record = migration_record_factory(billing_transfer_start_date="2026-10-01")
    mock_migration_table.get_by_status.side_effect = [[record], []]
    mock_get_orders.return_value = [order_factory_sync()]

    processor.sync()  # act

    mock_aws_client.get_responsibility_transfer_details.assert_not_called()


def test_sync_skips_aws_when_order_not_accepted(
    processor,
    mock_migration_table,
    mock_get_orders,
    mock_aws_client,
    migration_record_factory,
    order_factory_sync,
):
    record = migration_record_factory()
    mock_migration_table.get_by_status.side_effect = [[record], []]
    mock_get_orders.return_value = [order_factory_sync(status=MptOrderStatus.DRAFT.value)]

    processor.sync()  # act

    mock_aws_client.get_responsibility_transfer_details.assert_not_called()


def test_sync_aws_error_keeps_other_changes_and_reports_row(
    processor,
    mock_migration_table,
    mock_get_orders,
    mock_aws_client,
    mock_teams,
    migration_record_factory,
    order_factory_sync,
):
    mock_aws_client.get_responsibility_transfer_details.side_effect = AWSError("access denied")
    record = migration_record_factory()
    mock_migration_table.get_by_status.side_effect = [[record], []]
    mock_get_orders.return_value = [order_factory_sync()]

    processor.sync()  # act

    mock_migration_table.save.assert_called_once_with(record)
    assert record.migration_status == AccountMigrationStatus.MIGRATION_IN_PROGRESS
    assert record.billing_transfer_start_date is None
    mock_teams.send_warning.assert_called_once_with(
        NOTIFICATION_TITLE,
        f"Rows checked: 1. Rows updated: 1. Rows with errors: 1.\n\nOrders with errors: {ORDER_ID}",
    )


def test_sync_reuses_aws_client_per_pma(
    mocker,
    processor,
    mock_migration_table,
    mock_get_orders,
    mock_aws_client,
    migration_record_factory,
    order_factory_sync,
):
    aws_client_class = mocker.patch(
        "swo_aws_extension.flows.jobs.migration_sync_processor.AWSClient",
        return_value=mock_aws_client,
    )
    mock_migration_table.get_by_status.side_effect = [
        [migration_record_factory(), migration_record_factory(mpt_order_id="ORD-2")],
        [],
    ]
    mock_get_orders.return_value = [order_factory_sync(), order_factory_sync(order_id="ORD-2")]

    processor.sync()  # act

    aws_client_class.assert_called_once()
    assert mock_aws_client.get_responsibility_transfer_details.call_count == 2


def test_sync_querying_order_keeps_existing_acceptance_date(
    processor, mock_migration_table, mock_get_orders, migration_record_factory, order_factory_sync
):
    record = migration_record_factory(
        migration_status=AccountMigrationStatus.MIGRATION_IN_PROGRESS,
        mpt_order_status=MptOrderStatus.PROCESSING.value,
        customer_accepted_date="2026-09-01",
    )
    mock_migration_table.get_by_status.side_effect = [[], [record]]
    mock_get_orders.return_value = [order_factory_sync(status=MptOrderStatus.QUERYING.value)]

    processor.sync()  # act

    mock_migration_table.save.assert_called_once_with(record)
    assert record.mpt_order_status == MptOrderStatus.QUERYING.value
    assert record.customer_accepted_date == "2026-09-01"
    assert record.migration_status == AccountMigrationStatus.MIGRATION_IN_PROGRESS


def test_sync_completed_order_sets_completed_status_and_date(
    processor, mock_migration_table, mock_get_orders, migration_record_factory, order_factory_sync
):
    record = migration_record_factory(
        migration_status=AccountMigrationStatus.MIGRATION_IN_PROGRESS,
        mpt_order_status=MptOrderStatus.PROCESSING.value,
        customer_accepted_date="2026-09-10",
    )
    mock_migration_table.get_by_status.side_effect = [[], [record]]
    mock_get_orders.return_value = [order_factory_sync(status=MptOrderStatus.COMPLETED.value)]

    processor.sync()  # act

    mock_migration_table.save.assert_called_once_with(record)
    assert record.mpt_order_status == MptOrderStatus.COMPLETED.value
    assert record.migration_status == AccountMigrationStatus.COMPLETED
    assert record.migration_completed_date == "2026-09-17"
    assert record.customer_accepted_date == "2026-09-10"


def test_sync_completed_order_sets_missing_acceptance_date(
    processor, mock_migration_table, mock_get_orders, migration_record_factory, order_factory_sync
):
    record = migration_record_factory()
    mock_migration_table.get_by_status.side_effect = [[record], []]
    mock_get_orders.return_value = [order_factory_sync(status=MptOrderStatus.COMPLETED.value)]

    processor.sync()  # act

    assert record.customer_accepted_date == "2026-09-10"
    assert record.migration_status == AccountMigrationStatus.COMPLETED


@pytest.mark.parametrize("status", [MptOrderStatus.FAILED.value, MptOrderStatus.DELETED.value])
def test_sync_failed_order_sets_failed_with_error(
    processor,
    mock_migration_table,
    mock_get_orders,
    migration_record_factory,
    order_factory_sync,
    status,
):
    record = migration_record_factory(migration_status=AccountMigrationStatus.MIGRATION_IN_PROGRESS)
    mock_migration_table.get_by_status.side_effect = [[], [record]]
    mock_get_orders.return_value = [
        order_factory_sync(status=status, error={"id": "AWS001", "message": "Invitation declined"})
    ]

    processor.sync()  # act

    mock_migration_table.save.assert_called_once_with(record)
    assert record.mpt_order_status == MptOrderStatus.FAILED.value
    assert record.migration_status == AccountMigrationStatus.FAILED
    assert record.error == "Invitation declined"


def test_sync_missing_order_marks_row_failed(
    processor, mock_migration_table, mock_get_orders, migration_record_factory
):
    record = migration_record_factory()
    mock_migration_table.get_by_status.side_effect = [[record], []]
    mock_get_orders.return_value = []

    processor.sync()  # act

    mock_migration_table.save.assert_called_once_with(record)
    assert record.mpt_order_status == MptOrderStatus.FAILED.value
    assert record.migration_status == AccountMigrationStatus.FAILED
    assert record.error == f"Order {ORDER_ID} not found in the marketplace"


def test_sync_draft_order_only_mirrors_status(
    processor, mock_migration_table, mock_get_orders, migration_record_factory, order_factory_sync
):
    record = migration_record_factory(mpt_order_status=None)
    mock_migration_table.get_by_status.side_effect = [[record], []]
    mock_get_orders.return_value = [order_factory_sync(status=MptOrderStatus.DRAFT.value)]

    processor.sync()  # act

    mock_migration_table.save.assert_called_once_with(record)
    assert record.mpt_order_status == MptOrderStatus.DRAFT.value
    assert record.migration_status == AccountMigrationStatus.PENDING_NOTIFY_CUSTOMER
    assert record.customer_accepted_date is None


def test_sync_skips_save_when_row_is_up_to_date(
    processor, mock_migration_table, mock_get_orders, migration_record_factory, order_factory_sync
):
    record = migration_record_factory()
    mock_migration_table.get_by_status.side_effect = [[record], []]
    mock_get_orders.return_value = [order_factory_sync(status=MptOrderStatus.DRAFT.value)]

    processor.sync()  # act

    mock_migration_table.save.assert_not_called()


def test_sync_dry_run_does_not_save(
    mpt_client,
    config,
    mock_migration_table,
    mock_get_orders,
    mock_teams,
    mock_aws_client,
    migration_record_factory,
    order_factory_sync,
):
    record = migration_record_factory()
    mock_migration_table.get_by_status.side_effect = [[record], []]
    mock_get_orders.return_value = [order_factory_sync(status=MptOrderStatus.COMPLETED.value)]
    processor = MigrationOrdersSyncProcessor(mpt_client, config, dry_run=True)

    processor.sync()  # act

    mock_migration_table.save.assert_not_called()
    assert record.migration_status == AccountMigrationStatus.PENDING_NOTIFY_CUSTOMER
    mock_teams.send_success.assert_called_once_with(
        NOTIFICATION_TITLE, "Dry run. Rows checked: 1. Rows updated: 0. Rows with errors: 0."
    )


def test_sync_reports_updated_rows(
    processor,
    mock_migration_table,
    mock_get_orders,
    mock_teams,
    migration_record_factory,
    order_factory_sync,
):
    mock_migration_table.get_by_status.side_effect = [
        [migration_record_factory(), migration_record_factory(mpt_order_id="ORD-2")],
        [],
    ]
    mock_get_orders.return_value = [
        order_factory_sync(),
        order_factory_sync(order_id="ORD-2", status=MptOrderStatus.DRAFT.value),
    ]

    processor.sync()  # act

    mock_teams.send_success.assert_called_once_with(
        NOTIFICATION_TITLE, "Rows checked: 2. Rows updated: 1. Rows with errors: 0."
    )
    mock_teams.send_warning.assert_not_called()


def test_sync_continues_and_reports_when_a_row_fails(
    processor,
    mock_migration_table,
    mock_get_orders,
    mock_teams,
    migration_record_factory,
    order_factory_sync,
):
    failing = migration_record_factory()
    healthy = migration_record_factory(mpt_order_id="ORD-2")
    mock_migration_table.get_by_status.side_effect = [[failing, healthy], []]
    mock_get_orders.return_value = [order_factory_sync(), order_factory_sync(order_id="ORD-2")]
    mock_migration_table.save.side_effect = [RuntimeError("airtable down"), healthy]

    processor.sync()  # act

    assert mock_migration_table.save.call_count == 2
    mock_teams.send_warning.assert_called_once_with(
        NOTIFICATION_TITLE,
        f"Rows checked: 2. Rows updated: 1. Rows with errors: 1.\n\nOrders with errors: {ORDER_ID}",
    )
    mock_teams.send_success.assert_not_called()
