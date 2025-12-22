from swo_aws_extension.airtable.models import (
    OpScaleFields,
    OpScaleRecord,
)


def test_op_scale_from_airtable_record():
    record = {
        "id": "rec123456",
        "fields": {
            "Account ID": "123456789123",
            "Buyer ID": "BUY-1111-1111",
            "Agreement ID": "AGR-0001",
            "Status": "ACTIVE",
            "Last Usage Date": "2025-12-26",
        },
    }

    result = OpScaleRecord.from_airtable_record(record)

    expected_result = OpScaleRecord(
        record_id="rec123456",
        account_id="123456789123",
        buyer_id="BUY-1111-1111",
        agreement_id="AGR-0001",
        status="ACTIVE",
        last_usage_date="2025-12-26",
    )
    assert result == expected_result


def test_op_scale_from_airtable_missing():
    record = {"fields": {}}

    result = OpScaleRecord.from_airtable_record(record)

    expected_result = OpScaleRecord(
        record_id=None,
        account_id=None,
        buyer_id=None,
        agreement_id=None,
        status=None,
        last_usage_date=None,
    )
    assert result == expected_result


def test_op_scale_to_airtable_fields():
    record = OpScaleRecord(
        account_id="123456789123",
        buyer_id="BUY-1111-1111",
        agreement_id="AGR-0001",
        status="ACTIVE",
        last_usage_date="2025-12-26",
    )

    result = record.to_airtable_fields()

    assert result == {
        OpScaleFields.ACCOUNT_ID: "123456789123",
        OpScaleFields.BUYER_ID: "BUY-1111-1111",
        OpScaleFields.AGREEMENT_ID: "AGR-0001",
        OpScaleFields.STATUS: "ACTIVE",
        OpScaleFields.LAST_USAGE_DATE: "2025-12-26",
    }


def test_op_scale_to_airtable_partial():
    record = OpScaleRecord(
        account_id="123456789123",
        status="ACTIVE",
    )

    result = record.to_airtable_fields()

    assert result == {
        OpScaleFields.ACCOUNT_ID: "123456789123",
        OpScaleFields.STATUS: "ACTIVE",
    }


def test_op_scale_is_new_true():
    result = OpScaleRecord(
        account_id="123456789123",
        buyer_id="BUY-1111-1111",
    )

    assert result.is_new() is True


def test_op_scale_is_new_false():
    result = OpScaleRecord(
        record_id="rec123456",
        account_id="123456789123",
        buyer_id="BUY-1111-1111",
    )

    assert result.is_new() is False


def test_op_scale_record():
    record = {
        "fields": {
            "Account ID": "123456789123",
            "Buyer ID": "BUY-1111-1111",
            "Agreement ID": None,
            "Status": None,
            "Created": None,
            "Last Usage Date": None,
        }
    }

    result = OpScaleRecord.from_airtable_record(record)

    expected_result = OpScaleRecord(
        account_id="123456789123",
        buyer_id="BUY-1111-1111",
        agreement_id=None,
        status=None,
        last_usage_date=None,
    )
    assert result == expected_result


def test_op_scale_record_missing_fields():
    record = {"fields": {}}

    result = OpScaleRecord.from_airtable_record(record)

    expected_result = OpScaleRecord(
        account_id=None,
        buyer_id=None,
        agreement_id=None,
        status=None,
        last_usage_date=None,
    )
    assert result == expected_result
