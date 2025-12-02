from swo_aws_extension.airtable.models import (
    PMARecord,
)


def test_pma_record():
    record = {
        "fields": {
            "Authorization ID": "AUTH-1111-1111",
            "PMA Account ID": "123456789123",
            "PMA ID": "pma-1k5fapyt9osi1",
            "PMA Name": "Billing Transfer",
            "PMA Email": "test@example.com",
            "Currency": "USD",
            "Country": "US",
            "Primary Account": True,
        }
    }

    result = PMARecord.from_airtable_record(record)

    expected_result = PMARecord(
        authorization_id="AUTH-1111-1111",
        pma_account_id="123456789123",
        pma_id="pma-1k5fapyt9osi1",
        pma_name="Billing Transfer",
        pma_email="test@example.com",
        currency="USD",
        country="US",
        primary_account=True,
    )
    assert result == expected_result


def test_pma_record_missing_fields():
    record = {"fields": {}}

    result = PMARecord.from_airtable_record(record)

    expected_result = PMARecord(
        authorization_id=None,
        pma_account_id=None,
        pma_id=None,
        pma_name=None,
        pma_email=None,
        currency=None,
        country=None,
        primary_account=False,
    )
    assert result == expected_result
