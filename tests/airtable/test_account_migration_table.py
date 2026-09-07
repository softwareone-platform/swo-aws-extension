import pytest
from pyairtable import Table

from swo_aws_extension.airtable.account_migration_table import AwsAccountMigrationTable
from swo_aws_extension.airtable.models import (
    AccountMigrationFields,
    AccountMigrationRecord,
    AccountMigrationStatus,
)


@pytest.fixture
def mock_api_table(mocker):
    table_instance = mocker.create_autospec(Table, instance=True)
    return mocker.patch(
        "swo_aws_extension.airtable.account_migration_table.Api.table",
        autospec=True,
        return_value=table_instance,
    )


@pytest.fixture
def mock_table(mock_api_table):
    return mock_api_table.return_value


@pytest.fixture
def account_migration_record_factory():
    def factory(**overrides):
        record_values = {
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
        }
        record_values.update(overrides)
        return AccountMigrationRecord(**record_values)

    return factory


def test_opens_account_migration_table_in_own_base(mock_api_table):
    AwsAccountMigrationTable()  # act

    assert mock_api_table.call_args.args[1:] == ("migration_base_id", "AWS Account Migration")


def test_get_by_status(mock_table):
    mock_table.all.return_value = [
        {
            "id": "rec123",
            "fields": {
                AccountMigrationFields.MASTERPAYER.value: "123456789012",
                AccountMigrationFields.MIGRATION_STATUS.value: "Processing",
            },
        }
    ]
    account_migration_table = AwsAccountMigrationTable()

    result = account_migration_table.get_by_status(AccountMigrationStatus.PROCESSING)

    assert [(record.record_id, record.migration_status) for record in result] == [
        ("rec123", "Processing")
    ]


def test_get_by_status_uses_status_formula(mock_table):
    mock_table.all.return_value = []
    account_migration_table = AwsAccountMigrationTable()

    account_migration_table.get_by_status(AccountMigrationStatus.ERROR)  # act

    assert str(mock_table.all.call_args.kwargs["formula"]) == "{Migration status}='Error'"


def test_get_by_order_id(mock_table):
    mock_table.all.return_value = [
        {
            "id": "rec123",
            "fields": {AccountMigrationFields.MPT_ORDER_ID.value: "ORD-1111-1111"},
        }
    ]
    account_migration_table = AwsAccountMigrationTable()

    result = account_migration_table.get_by_order_id("ORD-1111-1111")

    assert result.mpt_order_id == "ORD-1111-1111"


def test_get_by_order_id_uses_order_formula(mock_table):
    mock_table.all.return_value = []
    account_migration_table = AwsAccountMigrationTable()

    account_migration_table.get_by_order_id("ORD-1111-1111")  # act

    assert str(mock_table.all.call_args.kwargs["formula"]) == "{MPT Order ID}='ORD-1111-1111'"


def test_get_by_order_id_not_found(mock_table):
    mock_table.all.return_value = []
    account_migration_table = AwsAccountMigrationTable()

    result = account_migration_table.get_by_order_id("ORD-2222-2222")

    assert result is None


def test_get_by_billing_transfer_start_date(mock_table):
    mock_table.all.return_value = [
        {
            "id": "rec123",
            "fields": {AccountMigrationFields.BILLING_TRANSFER_START_DATE.value: "2026-10-01"},
        }
    ]
    account_migration_table = AwsAccountMigrationTable()

    result = account_migration_table.get_by_billing_transfer_start_date("2026-10-01")

    assert [record.billing_transfer_start_date for record in result] == ["2026-10-01"]


def test_get_by_billing_transfer_start_date_uses_date_formula(mock_table):
    mock_table.all.return_value = []
    account_migration_table = AwsAccountMigrationTable()

    account_migration_table.get_by_billing_transfer_start_date("2026-10-01")  # act

    assert (
        str(mock_table.all.call_args.kwargs["formula"])
        == "{Billing transfer start date}='2026-10-01'"
    )


def test_save_creates_new_record(mock_table, account_migration_record_factory):
    mock_table.create.return_value = {
        "id": "rec123",
        "fields": {
            AccountMigrationFields.MASTERPAYER.value: "123456789012",
            AccountMigrationFields.MIGRATION_STATUS.value: "Ready",
        },
    }
    account_migration_table = AwsAccountMigrationTable()
    new_record = account_migration_record_factory(migration_status=AccountMigrationStatus.READY)

    result = account_migration_table.save(new_record)

    mock_table.create.assert_called_once_with(new_record.to_airtable_fields())
    assert (result.record_id, result.masterpayer) == ("rec123", "123456789012")


def test_save_updates_existing_record(mock_table, account_migration_record_factory):
    mock_table.update.return_value = {
        "id": "rec123",
        "fields": {
            AccountMigrationFields.MASTERPAYER.value: "123456789012",
            AccountMigrationFields.MIGRATION_STATUS.value: "Completed",
        },
    }
    account_migration_table = AwsAccountMigrationTable()
    existing_record = account_migration_record_factory(
        record_id="rec123", migration_status=AccountMigrationStatus.COMPLETED
    )

    result = account_migration_table.save(existing_record)

    mock_table.update.assert_called_once_with("rec123", existing_record.to_airtable_fields())
    assert result.migration_status == "Completed"


def test_update_status(mock_table, account_migration_record_factory):
    mock_table.update.return_value = {
        "id": "rec123",
        "fields": {AccountMigrationFields.MIGRATION_STATUS.value: "Processing"},
    }
    account_migration_table = AwsAccountMigrationTable()
    existing_record = account_migration_record_factory(
        record_id="rec123", migration_status=AccountMigrationStatus.READY
    )

    result = account_migration_table.update_status(
        existing_record, AccountMigrationStatus.PROCESSING
    )

    updated_fields = mock_table.update.call_args.args[1]
    assert (updated_fields[AccountMigrationFields.MIGRATION_STATUS], result.migration_status) == (
        AccountMigrationStatus.PROCESSING,
        "Processing",
    )


def test_update_status_with_error(mock_table, account_migration_record_factory):
    mock_table.update.return_value = {
        "id": "rec123",
        "fields": {
            AccountMigrationFields.MIGRATION_STATUS.value: "Error",
            AccountMigrationFields.ERROR.value: "Buyer not found",
        },
    }
    account_migration_table = AwsAccountMigrationTable()
    existing_record = account_migration_record_factory(
        record_id="rec123", migration_status=AccountMigrationStatus.PROCESSING
    )

    result = account_migration_table.update_status(
        existing_record, AccountMigrationStatus.ERROR, error="Buyer not found"
    )

    assert (result.migration_status, result.error) == ("Error", "Buyer not found")


def test_update_status_without_error_keeps_previous_error(
    mock_table, account_migration_record_factory
):
    mock_table.update.return_value = {"id": "rec123", "fields": {}}
    account_migration_table = AwsAccountMigrationTable()
    existing_record = account_migration_record_factory(
        record_id="rec123", migration_status=AccountMigrationStatus.ERROR, error="Previous error"
    )

    account_migration_table.update_status(existing_record, AccountMigrationStatus.READY)  # act

    updated_fields = mock_table.update.call_args.args[1]
    assert updated_fields[AccountMigrationFields.ERROR] == "Previous error"
