import pytest

from swo_aws_extension.airtable.models import (
    AccountMigrationFields,
    AccountMigrationOrderStatus,
    AccountMigrationRecord,
    AccountMigrationStatus,
    FinOpsFields,
    FinOpsRecord,
)


def test_finops_from_airtable_record():
    record = {
        "id": "rec123456",
        "fields": {
            "Account ID": "123456789123",
            "Buyer ID": "BUY-1111-1111",
            "Agreement ID": "AGR-0001",
            "Entitlement ID": "ENT-0001",
            "Status": "ACTIVE",
            "Last Usage Date": "2025-12-26",
        },
    }

    result = FinOpsRecord.from_airtable_record(record)

    expected_result = FinOpsRecord(
        record_id="rec123456",
        account_id="123456789123",
        buyer_id="BUY-1111-1111",
        agreement_id="AGR-0001",
        entitlement_id="ENT-0001",
        status="ACTIVE",
        last_usage_date="2025-12-26",
    )
    assert result == expected_result


def test_finops_to_airtable_fields():
    record = FinOpsRecord(
        account_id="123456789123",
        buyer_id="BUY-1111-1111",
        agreement_id="AGR-0001",
        entitlement_id="ENT-0001",
        status="ACTIVE",
        last_usage_date="2025-12-26",
    )

    result = record.to_airtable_fields()

    assert result == {
        FinOpsFields.ACCOUNT_ID: "123456789123",
        FinOpsFields.BUYER_ID: "BUY-1111-1111",
        FinOpsFields.AGREEMENT_ID: "AGR-0001",
        FinOpsFields.ENTITLEMENT_ID: "ENT-0001",
        FinOpsFields.STATUS: "ACTIVE",
        FinOpsFields.LAST_USAGE_DATE: "2025-12-26",
    }


def test_finops_is_new_true():
    result = FinOpsRecord(
        account_id="123456789123",
        buyer_id="BUY-1111-1111",
        agreement_id="AGR-0001",
        entitlement_id="ENT-0001",
        status="ACTIVE",
        last_usage_date="2025-12-26",
    )

    assert result.is_new() is True


def test_finops_is_new_false():
    result = FinOpsRecord(
        record_id="rec123456",
        account_id="123456789123",
        buyer_id="BUY-1111-1111",
        agreement_id="AGR-0001",
        entitlement_id="ENT-0001",
        status="ACTIVE",
        last_usage_date="2025-12-26",
    )

    assert result.is_new() is False


@pytest.fixture
def account_migration_airtable_fields():
    return {
        "SWO Seller": "SEL-1111-1111",
        "SWO Buyer": "BUY-1111-1111",
        "Masterpayer": "123456789012",
        "MPT CCO": "CCO-0001",
        "AWS account email": "root@example.com",
        "AWS support type": "resoldSupport",
        "SWO support discount": 0.5,
        "SWO usage discount": 3,
        "Technical contact name": "Jane Doe",
        "Technical contact email": "jane.doe@example.com",
        "Technical phone": "+34600000000",
        "Group": "Group A",
        "Batch": "Batch 1",
        "Migration status": "Pending notify customer",
        "MPT Order ID": "ORD-1111-1111",
        "MPT Order status": "Draft",
        "Order creation date": "2026-09-04",
        "Customer accepted date": "2026-09-05",
        "Migration completed date": "2026-09-06",
        "Billing transfer start date": "2026-10-01",
        "Batch group number": 1,
        "Error": "Some error",
    }


@pytest.fixture
def account_migration_record():
    return AccountMigrationRecord(
        record_id="rec123456",
        swo_seller="SEL-1111-1111",
        swo_buyer="BUY-1111-1111",
        masterpayer="123456789012",
        mpt_cco="CCO-0001",
        aws_account_email="root@example.com",
        aws_support_type="resoldSupport",
        swo_support_discount=0.5,
        swo_usage_discount=3,
        technical_contact_name="Jane Doe",
        technical_contact_email="jane.doe@example.com",
        technical_phone="+34600000000",
        group="Group A",
        batch="Batch 1",
        migration_status="Pending notify customer",
        mpt_order_id="ORD-1111-1111",
        mpt_order_status="Draft",
        order_creation_date="2026-09-04",
        customer_accepted_date="2026-09-05",
        migration_completed_date="2026-09-06",
        billing_transfer_start_date="2026-10-01",
        batch_group_number=1,
        error="Some error",
    )


def test_account_migration_from_airtable_record(
    account_migration_airtable_fields, account_migration_record
):
    record = {"id": "rec123456", "fields": account_migration_airtable_fields}

    result = AccountMigrationRecord.from_airtable_record(record)

    assert result == account_migration_record


def test_account_migration_from_airtable_record_without_state_columns():
    record = {
        "id": "rec123456",
        "fields": {
            "SWO Seller": "SEL-1111-1111",
            "SWO Buyer": "BUY-1111-1111",
            "Masterpayer": "123456789012",
            "MPT CCO": "CCO-0001",
            "AWS account email": "root@example.com",
            "AWS support type": "partnerLedSupport",
            "Technical contact name": "Jane Doe",
            "Technical contact email": "jane.doe@example.com",
            "Group": "Group A",
            "Batch": "Batch 1",
        },
    }

    result = AccountMigrationRecord.from_airtable_record(record)

    assert result == AccountMigrationRecord(
        record_id="rec123456",
        swo_seller="SEL-1111-1111",
        swo_buyer="BUY-1111-1111",
        masterpayer="123456789012",
        mpt_cco="CCO-0001",
        aws_account_email="root@example.com",
        aws_support_type="partnerLedSupport",
        technical_contact_name="Jane Doe",
        technical_contact_email="jane.doe@example.com",
        group="Group A",
        batch="Batch 1",
    )


def test_account_migration_to_airtable_fields(
    account_migration_airtable_fields, account_migration_record
):
    result = account_migration_record.to_airtable_fields()

    assert result == account_migration_airtable_fields


def test_account_migration_to_airtable_fields_skips_empty_values():
    record = AccountMigrationRecord(
        swo_seller="SEL-1111-1111",
        swo_buyer="BUY-1111-1111",
        masterpayer="123456789012",
        mpt_cco="CCO-0001",
        aws_account_email="root@example.com",
        aws_support_type="resoldSupport",
        technical_contact_name="Jane Doe",
        technical_contact_email="jane.doe@example.com",
        group="Group A",
        batch="Batch 1",
        migration_status=AccountMigrationStatus.READY,
    )

    result = record.to_airtable_fields()

    assert result == {
        AccountMigrationFields.SWO_SELLER: "SEL-1111-1111",
        AccountMigrationFields.SWO_BUYER: "BUY-1111-1111",
        AccountMigrationFields.MASTERPAYER: "123456789012",
        AccountMigrationFields.MPT_CCO: "CCO-0001",
        AccountMigrationFields.AWS_ACCOUNT_EMAIL: "root@example.com",
        AccountMigrationFields.AWS_SUPPORT_TYPE: "resoldSupport",
        AccountMigrationFields.TECHNICAL_CONTACT_NAME: "Jane Doe",
        AccountMigrationFields.TECHNICAL_CONTACT_EMAIL: "jane.doe@example.com",
        AccountMigrationFields.GROUP: "Group A",
        AccountMigrationFields.BATCH: "Batch 1",
        AccountMigrationFields.MIGRATION_STATUS: AccountMigrationStatus.READY,
    }


@pytest.mark.parametrize(
    ("record_id", "expected"),
    [
        (None, True),
        ("rec123456", False),
    ],
)
def test_account_migration_is_new(record_id, expected):
    record = AccountMigrationRecord(
        record_id=record_id,
        swo_seller="SEL-1111-1111",
        swo_buyer="BUY-1111-1111",
        masterpayer="123456789012",
        mpt_cco="CCO-0001",
        aws_account_email="root@example.com",
        aws_support_type="resoldSupport",
        technical_contact_name="Jane Doe",
        technical_contact_email="jane.doe@example.com",
        group="Group A",
        batch="Batch 1",
    )

    result = record.is_new()

    assert result is expected


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (AccountMigrationStatus.READY, "Ready"),
        (AccountMigrationStatus.PROCESSING, "Processing"),
        (AccountMigrationStatus.PENDING_NOTIFY_CUSTOMER, "Pending notify customer"),
        (AccountMigrationStatus.MIGRATION_IN_PROGRESS, "Migration in progress"),
        (AccountMigrationStatus.COMPLETED, "Completed"),
        (AccountMigrationStatus.SERVICES_ONBOARDED, "Services onboarded"),
        (AccountMigrationStatus.ERROR, "Error"),
        (AccountMigrationStatus.FAILED, "Failed"),
    ],
)
def test_account_migration_status_values(status, expected):
    result = status.value

    assert result == expected


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (AccountMigrationOrderStatus.DRAFT, "Draft"),
        (AccountMigrationOrderStatus.PROCESSING, "Processing"),
        (AccountMigrationOrderStatus.QUERYING, "Querying"),
        (AccountMigrationOrderStatus.COMPLETED, "Completed"),
        (AccountMigrationOrderStatus.FAILED, "Failed"),
    ],
)
def test_account_migration_order_status_values(status, expected):
    result = status.value

    assert result == expected
