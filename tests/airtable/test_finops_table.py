from unittest.mock import patch

import pytest
from pyairtable import Table

from swo_aws_extension.airtable.finops_table import FinOpsEntitlementsTable
from swo_aws_extension.airtable.models import FinOpsFields, FinOpsRecord


@pytest.fixture
def mock_get_for_product():
    with patch("swo_aws_extension.airtable.finops_table.get_for_product", return_value="base-id"):
        yield


@pytest.fixture
def mock_table(mocker):
    with patch("swo_aws_extension.airtable.finops_table.Api.table") as table_cls:
        table_instance = mocker.MagicMock(spec=Table)
        table_cls.return_value = table_instance
        yield table_instance


def test_get_by_agreement_id(mock_get_for_product, mock_table):
    table_instance = mock_table
    table_instance.all.return_value = [
        {
            "id": "rec123",
            "fields": {
                FinOpsFields.AGREEMENT_ID.value: "AGR-1111-1111",
            },
        }
    ]
    finops_table = FinOpsEntitlementsTable()

    result = finops_table.get_by_agreement_id("AGR-1111-1111")

    assert result[0].agreement_id == "AGR-1111-1111"


def test_get_by_agreement_id_no_records(mock_get_for_product, mock_table):
    table_instance = mock_table
    table_instance.all.return_value = []
    finops_table = FinOpsEntitlementsTable()

    result = finops_table.get_by_agreement_id("AGR-2222-2222")

    assert result == []


def test_save_creates_new_record(mock_get_for_product, mock_table):
    table_instance = mock_table
    table_instance.create.return_value = {
        "id": "rec123",
        "fields": {
            FinOpsFields.ACCOUNT_ID.value: "123456789",
            FinOpsFields.AGREEMENT_ID.value: "AGR-1111-1111",
            FinOpsFields.STATUS.value: "ACTIVE",
        },
    }
    finops_table = FinOpsEntitlementsTable()
    new_record = FinOpsRecord(
        account_id="123456789",
        agreement_id="AGR-1111-1111",
        status="ACTIVE",
        entitlement_id="ENT-0001",
        buyer_id="123456789",
        last_usage_date="2025-12-26T00:00:00+00:00",
    )

    result = finops_table.save(new_record)

    table_instance.create.assert_called_once()
    assert result.record_id == "rec123"
    assert result.account_id == "123456789"


def test_save_updates_existing_record(mock_get_for_product, mock_table):
    table_instance = mock_table
    table_instance.update.return_value = {
        "id": "rec123",
        "fields": {
            FinOpsFields.ACCOUNT_ID.value: "123456789",
            FinOpsFields.AGREEMENT_ID.value: "AGR-1111-1111",
            FinOpsFields.STATUS.value: "TERMINATED",
        },
    }
    finops_table = FinOpsEntitlementsTable()
    existing_record = FinOpsRecord(
        record_id="rec123",
        account_id="123456789",
        agreement_id="AGR-1111-1111",
        status="TERMINATED",
        entitlement_id="ENT-0001",
        buyer_id="123456789",
        last_usage_date="2025-12-26T00:00:00+00:00",
    )

    result = finops_table.save(existing_record)

    table_instance.update.assert_called_once_with("rec123", existing_record.to_airtable_fields())
    assert result.status == "TERMINATED"


def test_update_status_and_usage_date(mock_get_for_product, mock_table):
    table_instance = mock_table
    table_instance.update.return_value = {
        "id": "rec123",
        "fields": {
            FinOpsFields.ACCOUNT_ID.value: "123456789",
            FinOpsFields.STATUS.value: "TERMINATED",
            FinOpsFields.LAST_USAGE_DATE.value: "2025-12-26T00:00:00+00:00",
        },
    }
    finops_table = FinOpsEntitlementsTable()
    existing_record = FinOpsRecord(
        record_id="rec123",
        account_id="123456789",
        status="ACTIVE",
        last_usage_date="2025-10-01T00:00:00+00:00",
        agreement_id="AGR-1111-1111",
        entitlement_id="ENT-0001",
        buyer_id="123456789",
    )

    result = finops_table.update_status_and_usage_date(
        existing_record, "TERMINATED", "2025-12-26T00:00:00+00:00"
    )

    table_instance.update.assert_called_once()
    assert result.status == "TERMINATED"
    assert result.last_usage_date == "2025-12-26T00:00:00+00:00"
