import datetime as dt
from http import HTTPStatus

import pytest
from mpt_api_client.exceptions import MPTError

from swo_aws_extension.airtable.models import AccountMigrationRecord, AccountMigrationStatus
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.constants import (
    FulfillmentParametersEnum,
    MptOrderStatus,
    ParamPhasesEnum,
    ResponsibilityTransferStatus,
)
from swo_aws_extension.flows.jobs.migration_sync_processor import (
    NOTIFICATION_TITLE,
    ORDERS_QUERY_SELECT,
    SYNCABLE_MIGRATION_STATUSES,
    MigrationOrdersSyncProcessor,
    get_audit_date,
    get_iso_date,
    get_order_error,
)
from swo_aws_extension.flows.steps.crm_tickets.templates.billing_transfer_start import (
    BILLING_TRANSFER_START_TEMPLATE,
)
from swo_aws_extension.swo.crm_service.client import ServiceRequest
from swo_aws_extension.swo.crm_service.errors import CRMError
from swo_aws_extension.swo.mpt.order import ORDERS_QUERY_BATCH_SIZE

ORDER_ID = "ORD-0792-5000-2253-4210"
PROCESSING_AT = "2026-09-10T08:15:00.000Z"
COMPLETED_AT = "2026-09-17T16:40:00.000Z"
UPDATED_AT = "2026-09-18T09:00:00.000Z"
TRANSFER_ID = "rt-8lr3q6sn"
PMA_ACCOUNT_ID = "123456789012"
TRANSFER_START = dt.datetime.fromisoformat("2026-10-01T00:00:00+00:00")
RUN_DATE = dt.date.fromisoformat("2026-09-21")
AGREEMENT_ID = "AGR-2119-4550-8674-5962"
TICKET_ID = "CS0004728"


@pytest.fixture
def mock_migration_table(mocker):
    mock_table = mocker.MagicMock()
    mock_table.get_by_statuses.return_value = []
    mocker.patch(
        "swo_aws_extension.flows.jobs.migration_sync_processor.AwsAccountMigrationTable",
        return_value=mock_table,
    )
    return mock_table


@pytest.fixture
def mock_get_orders(mocker):
    return mocker.patch(
        "swo_aws_extension.swo.mpt.order.get_orders_by_query",
        return_value=[],
    )


@pytest.fixture
def mock_teams(mocker):
    return mocker.patch(
        "swo_aws_extension.flows.jobs.migration_sync_processor.TeamsNotificationManager"
    ).return_value


@pytest.fixture
def mock_update_agreement(mocker):
    return mocker.patch(
        "swo_aws_extension.flows.jobs.migration_billing_transfer_ticket.update_agreement"
    )


@pytest.fixture
def mock_crm(mocker):
    mock_client = mocker.patch(
        "swo_aws_extension.flows.jobs.migration_billing_transfer_ticket.get_service_client"
    ).return_value
    mock_client.create_service_request.return_value = {"id": TICKET_ID}
    return mock_client


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
def order_factory_sync(buyer, seller, fulfillment_parameters_factory):
    def factory(
        status=MptOrderStatus.PROCESSING.value,
        order_id=ORDER_ID,
        audit=None,
        error=None,
        transfer_id=TRANSFER_ID,
        pma_account_id=PMA_ACCOUNT_ID,
        agreement_ticket_id="",
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
            "agreement": {
                "id": AGREEMENT_ID,
                "parameters": {
                    "ordering": [],
                    "fulfillment": fulfillment_parameters_factory(
                        crm_migration_ticket_id=agreement_ticket_id
                    ),
                },
            },
            "buyer": buyer,
            "seller": seller,
        }

    return factory


@pytest.fixture
def processor(
    mpt_client,
    config,
    mock_migration_table,
    mock_get_orders,
    mock_teams,
    mock_aws_client,
    mock_crm,
    mock_update_agreement,
):
    return MigrationOrdersSyncProcessor(mpt_client, config, RUN_DATE)


@pytest.fixture
def completed_record(
    mock_migration_table, mock_get_orders, migration_record_factory, order_factory_sync
):
    record = migration_record_factory(
        migration_status=AccountMigrationStatus.COMPLETED,
        mpt_order_status=MptOrderStatus.COMPLETED.value,
        customer_accepted_date="2026-09-10",
        migration_completed_date="2026-09-17",
        billing_transfer_start_date="2026-09-01",
    )
    mock_migration_table.get_by_statuses.return_value = [record]
    mock_get_orders.return_value = [order_factory_sync(status=MptOrderStatus.COMPLETED.value)]
    return record


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


def test_sync_reads_pending_in_progress_and_completed_rows(processor, mock_migration_table):
    processor.sync()  # act

    mock_migration_table.get_by_statuses.assert_called_once_with(SYNCABLE_MIGRATION_STATUSES)
    assert SYNCABLE_MIGRATION_STATUSES == (
        AccountMigrationStatus.PENDING_NOTIFY_CUSTOMER,
        AccountMigrationStatus.MIGRATION_IN_PROGRESS,
        AccountMigrationStatus.COMPLETED,
    )


def test_sync_skips_rows_without_order_and_queries_nothing(
    processor, mock_migration_table, mock_get_orders, mock_teams, migration_record_factory
):
    mock_migration_table.get_by_statuses.return_value = [
        migration_record_factory(mpt_order_id=None)
    ]

    processor.sync()  # act

    mock_get_orders.assert_not_called()
    mock_migration_table.save.assert_not_called()
    mock_teams.send_success.assert_called_once_with(
        NOTIFICATION_TITLE,
        "Rows checked: 0. Rows updated: 0. Tickets created: 0. Rows with errors: 0.",
    )


def test_sync_queries_orders_by_id_with_audit(
    processor, mock_migration_table, mock_get_orders, migration_record_factory, order_factory_sync
):
    mock_migration_table.get_by_statuses.return_value = [
        migration_record_factory(),
        migration_record_factory(mpt_order_id="ORD-2"),
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
    mock_migration_table.get_by_statuses.return_value = [record]
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
    mock_migration_table.get_by_statuses.return_value = [record]
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
    mock_migration_table.get_by_statuses.return_value = [record]
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
    mock_migration_table.get_by_statuses.return_value = [record]
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
    mock_migration_table.get_by_statuses.return_value = [record]
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
    mock_migration_table.get_by_statuses.return_value = [record]
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
    mock_migration_table.get_by_statuses.return_value = [record]
    mock_get_orders.return_value = [order_factory_sync()]

    processor.sync()  # act

    mock_migration_table.save.assert_called_once_with(record)
    assert record.migration_status == AccountMigrationStatus.MIGRATION_IN_PROGRESS
    assert record.billing_transfer_start_date is None
    mock_teams.send_warning.assert_called_once_with(
        NOTIFICATION_TITLE,
        "Rows checked: 1. Rows updated: 1. Tickets created: 0. Rows with errors: 1."
        f"\n\nOrders with errors: {ORDER_ID}",
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
    mock_migration_table.get_by_statuses.return_value = [
        migration_record_factory(),
        migration_record_factory(mpt_order_id="ORD-2"),
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
    mock_migration_table.get_by_statuses.return_value = [record]
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
    mock_migration_table.get_by_statuses.return_value = [record]
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
    mock_migration_table.get_by_statuses.return_value = [record]
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
    mock_migration_table.get_by_statuses.return_value = [record]
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
    mock_migration_table.get_by_statuses.return_value = [record]
    mock_get_orders.return_value = []

    processor.sync()  # act

    mock_migration_table.save.assert_called_once_with(record)
    assert record.mpt_order_status == MptOrderStatus.FAILED.value
    assert record.migration_status == AccountMigrationStatus.FAILED
    assert record.error == f"Order {ORDER_ID} not found in the marketplace"


@pytest.mark.parametrize("status", [MptOrderStatus.DRAFT.value, MptOrderStatus.QUOTED.value])
def test_sync_not_accepted_order_only_mirrors_status(
    processor,
    mock_migration_table,
    mock_get_orders,
    migration_record_factory,
    order_factory_sync,
    status,
):
    record = migration_record_factory(mpt_order_status=None)
    mock_migration_table.get_by_statuses.return_value = [record]
    mock_get_orders.return_value = [order_factory_sync(status=status)]

    processor.sync()  # act

    mock_migration_table.save.assert_called_once_with(record)
    assert record.mpt_order_status == status
    assert record.migration_status == AccountMigrationStatus.PENDING_NOTIFY_CUSTOMER
    assert record.customer_accepted_date is None


def test_sync_skips_save_when_row_is_up_to_date(
    processor, mock_migration_table, mock_get_orders, migration_record_factory, order_factory_sync
):
    record = migration_record_factory()
    mock_migration_table.get_by_statuses.return_value = [record]
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
    mock_migration_table.get_by_statuses.return_value = [record]
    mock_get_orders.return_value = [order_factory_sync(status=MptOrderStatus.COMPLETED.value)]
    processor = MigrationOrdersSyncProcessor(mpt_client, config, RUN_DATE, dry_run=True)

    processor.sync()  # act

    mock_migration_table.save.assert_not_called()
    assert record.migration_status == AccountMigrationStatus.PENDING_NOTIFY_CUSTOMER
    mock_teams.send_success.assert_called_once_with(
        NOTIFICATION_TITLE,
        "Dry run. Rows checked: 1. Rows updated: 0. Tickets created: 0. Rows with errors: 0.",
    )


def test_sync_reports_updated_rows(
    processor,
    mock_migration_table,
    mock_get_orders,
    mock_teams,
    migration_record_factory,
    order_factory_sync,
):
    mock_migration_table.get_by_statuses.return_value = [
        migration_record_factory(),
        migration_record_factory(mpt_order_id="ORD-2"),
    ]
    mock_get_orders.return_value = [
        order_factory_sync(),
        order_factory_sync(order_id="ORD-2", status=MptOrderStatus.DRAFT.value),
    ]

    processor.sync()  # act

    mock_teams.send_success.assert_called_once_with(
        NOTIFICATION_TITLE,
        "Rows checked: 2. Rows updated: 1. Tickets created: 0. Rows with errors: 0.",
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
    mock_migration_table.get_by_statuses.return_value = [failing, healthy]
    mock_get_orders.return_value = [order_factory_sync(), order_factory_sync(order_id="ORD-2")]
    mock_migration_table.save.side_effect = [RuntimeError("airtable down"), healthy]

    processor.sync()  # act

    assert mock_migration_table.save.call_count == 2
    mock_teams.send_warning.assert_called_once_with(
        NOTIFICATION_TITLE,
        "Rows checked: 2. Rows updated: 1. Tickets created: 0. Rows with errors: 1."
        f"\n\nOrders with errors: {ORDER_ID}",
    )
    mock_teams.send_success.assert_not_called()


def test_sync_completed_row_with_effective_transfer_creates_ticket(
    processor, completed_record, mock_migration_table, mock_crm, mock_teams, buyer
):
    processor.sync()  # act

    expected_service_request = ServiceRequest(
        additional_info=BILLING_TRANSFER_START_TEMPLATE.additional_info,
        summary=BILLING_TRANSFER_START_TEMPLATE.summary.format(
            customer_name=buyer["name"],
            buyer_id=buyer["id"],
            buyer_external_id=buyer["externalIds"]["erpCustomer"],
            seller_country="US",
            order_id=ORDER_ID,
            agreement_id=AGREEMENT_ID,
            master_payer_id="123456789012",
            cco_contract_number="CCO-0001",
            billing_transfer_start_date="2026-09-01",
            technical_contact_name="Jane Doe",
            technical_contact_email="jane.doe@example.com",
            technical_contact_phone="N/A",
            support_type="resoldSupport",
        ),
        title=BILLING_TRANSFER_START_TEMPLATE.title,
    )
    mock_crm.create_service_request.assert_called_once_with(ORDER_ID, expected_service_request)
    mock_migration_table.save.assert_called_once_with(completed_record)
    assert completed_record.migration_status == AccountMigrationStatus.SERVICES_ONBOARDED
    mock_teams.send_success.assert_called_once_with(
        NOTIFICATION_TITLE,
        "Rows checked: 1. Rows updated: 1. Tickets created: 1. Rows with errors: 0.",
    )


def test_sync_ticket_clears_previous_error_and_uses_start_date_of_run_date(
    processor, completed_record, mock_crm
):
    completed_record.error = "previous failure"
    completed_record.billing_transfer_start_date = RUN_DATE.isoformat()

    processor.sync()  # act

    service_request = mock_crm.create_service_request.call_args.args[1]
    assert "<li><b>Billing Transfer Start Date:</b> 2026-09-21</li>" in service_request.summary
    assert not completed_record.error


def test_sync_order_completing_with_past_start_date_onboards_in_the_same_run(
    processor,
    mock_migration_table,
    mock_get_orders,
    mock_crm,
    migration_record_factory,
    order_factory_sync,
):
    record = migration_record_factory(
        migration_status=AccountMigrationStatus.MIGRATION_IN_PROGRESS,
        mpt_order_status=MptOrderStatus.PROCESSING.value,
        customer_accepted_date="2026-08-10",
        billing_transfer_start_date="2026-09-01",
    )
    mock_migration_table.get_by_statuses.return_value = [record]
    mock_get_orders.return_value = [order_factory_sync(status=MptOrderStatus.COMPLETED.value)]

    processor.sync()  # act

    mock_crm.create_service_request.assert_called_once()
    mock_migration_table.save.assert_called_once_with(record)
    assert record.mpt_order_status == MptOrderStatus.COMPLETED.value
    assert record.migration_completed_date == "2026-09-17"
    assert record.migration_status == AccountMigrationStatus.SERVICES_ONBOARDED


def test_sync_completed_row_fetches_missing_start_date_and_onboards(
    processor, completed_record, mock_aws_client, mock_crm
):
    completed_record.billing_transfer_start_date = None
    mock_aws_client.get_responsibility_transfer_details.return_value = {
        "ResponsibilityTransfer": {
            "Status": ResponsibilityTransferStatus.ACCEPTED,
            "StartTimestamp": dt.datetime.fromisoformat("2026-09-01T00:00:00+00:00"),
        }
    }

    processor.sync()  # act

    mock_aws_client.get_responsibility_transfer_details.assert_called_once_with(
        transfer_id=TRANSFER_ID
    )
    assert completed_record.billing_transfer_start_date == "2026-09-01"
    assert completed_record.migration_status == AccountMigrationStatus.SERVICES_ONBOARDED
    service_request = mock_crm.create_service_request.call_args.args[1]
    assert "<li><b>Billing Transfer Start Date:</b> 2026-09-01</li>" in service_request.summary


@pytest.mark.parametrize("start_date", ["2026-10-01", "not a date"])
def test_sync_completed_row_without_effective_transfer_is_left_untouched(
    processor, completed_record, mock_migration_table, mock_crm, start_date
):
    completed_record.billing_transfer_start_date = start_date

    processor.sync()  # act

    mock_crm.create_service_request.assert_not_called()
    mock_migration_table.save.assert_not_called()
    assert completed_record.migration_status == AccountMigrationStatus.COMPLETED


def test_sync_ticket_error_keeps_row_completed_for_the_next_run(
    processor, completed_record, mock_migration_table, mock_crm, mock_teams
):
    mock_crm.create_service_request.side_effect = CRMError(
        "crm down", HTTPStatus.SERVICE_UNAVAILABLE
    )

    processor.sync()  # act

    mock_migration_table.save.assert_called_once_with(completed_record)
    assert completed_record.migration_status == AccountMigrationStatus.COMPLETED
    assert completed_record.error == "CRMError (503): crm down"
    mock_teams.send_warning.assert_called_once_with(
        NOTIFICATION_TITLE,
        "Rows checked: 1. Rows updated: 1. Tickets created: 0. Rows with errors: 1."
        f"\n\nOrders with errors: {ORDER_ID}",
    )


def test_sync_dry_run_does_not_create_the_ticket(
    mpt_client,
    config,
    completed_record,
    mock_migration_table,
    mock_crm,
    mock_teams,
    mock_aws_client,
    mock_update_agreement,
):
    processor = MigrationOrdersSyncProcessor(mpt_client, config, RUN_DATE, dry_run=True)

    processor.sync()  # act

    mock_crm.create_service_request.assert_not_called()
    mock_update_agreement.assert_not_called()
    mock_migration_table.save.assert_not_called()
    assert completed_record.migration_status == AccountMigrationStatus.COMPLETED
    mock_teams.send_success.assert_called_once_with(
        NOTIFICATION_TITLE,
        "Dry run. Rows checked: 1. Rows updated: 0. Tickets created: 0. Rows with errors: 0.",
    )


def test_sync_stores_ticket_id_in_agreement(processor, completed_record, mock_update_agreement):
    processor.sync()  # act

    mock_update_agreement.assert_called_once_with(
        processor.mpt_client,
        AGREEMENT_ID,
        parameters={
            ParamPhasesEnum.FULFILLMENT.value: [
                {
                    "externalId": FulfillmentParametersEnum.CRM_MIGRATION_TICKET_ID.value,
                    "value": TICKET_ID,
                }
            ]
        },
    )


def test_sync_skips_ticket_already_stored_in_agreement(
    processor,
    completed_record,
    mock_get_orders,
    mock_migration_table,
    mock_crm,
    mock_update_agreement,
    mock_teams,
    order_factory_sync,
):
    mock_get_orders.return_value = [
        order_factory_sync(status=MptOrderStatus.COMPLETED.value, agreement_ticket_id=TICKET_ID)
    ]

    processor.sync()  # act

    mock_crm.create_service_request.assert_not_called()
    mock_update_agreement.assert_not_called()
    mock_migration_table.save.assert_called_once_with(completed_record)
    assert completed_record.migration_status == AccountMigrationStatus.SERVICES_ONBOARDED
    mock_teams.send_success.assert_called_once_with(
        NOTIFICATION_TITLE,
        "Rows checked: 1. Rows updated: 1. Tickets created: 0. Rows with errors: 0.",
    )


def test_sync_agreement_update_error_still_onboards_and_reports(
    processor, completed_record, mock_update_agreement, mock_teams
):
    mock_update_agreement.side_effect = MPTError("error")

    processor.sync()  # act

    assert completed_record.migration_status == AccountMigrationStatus.SERVICES_ONBOARDED
    mock_teams.send_warning.assert_called_once_with(
        NOTIFICATION_TITLE,
        "Rows checked: 1. Rows updated: 1. Tickets created: 1. Rows with errors: 1."
        f"\n\nOrders with errors: {ORDER_ID}",
    )


def test_sync_creates_ticket_when_agreement_has_no_parameters(
    processor, completed_record, mock_get_orders, mock_crm, order_factory_sync
):
    order = order_factory_sync(status=MptOrderStatus.COMPLETED.value)
    order["agreement"] = {"id": AGREEMENT_ID}
    mock_get_orders.return_value = [order]

    processor.sync()  # act

    mock_crm.create_service_request.assert_called_once()
    assert completed_record.migration_status == AccountMigrationStatus.SERVICES_ONBOARDED
