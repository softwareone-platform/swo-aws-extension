from swo_aws_extension.airtable.models import (
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
