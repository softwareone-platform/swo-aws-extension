from unittest.mock import patch

import pytest
from pyairtable import Table

from swo_aws_extension.airtable.errors import AirtableRecordNotFoundError
from swo_aws_extension.airtable.models import PMAFields
from swo_aws_extension.airtable.pma_table import ProgramManagementAccountTable


@pytest.fixture
def mock_get_for_product():
    with patch("swo_aws_extension.airtable.pma_table.get_for_product", return_value="base-id"):
        yield


@pytest.fixture
def mock_table(mocker):
    with patch("swo_aws_extension.airtable.pma_table.Table") as table_cls:
        table_instance = mocker.MagicMock(spec=Table)
        table_cls.return_value = table_instance
        yield table_instance


def test_get_by_auth_id_and_currency_ok(mock_get_for_product, mock_table):
    table_instance = mock_table
    table_instance.first.return_value = {
        "fields": {
            PMAFields.AUTHORIZATION_ID.value: "AUT-1111-1111",
            PMAFields.CURRENCY.value: "USD",
            PMAFields.PRIMARY_ACCOUNT.value: True,
        }
    }
    pma_table = ProgramManagementAccountTable()

    result = pma_table.get_by_authorization_and_currency_id("AUT-1111-1111", "USD")

    assert result.authorization_id == "AUT-1111-1111"
    assert result.currency == "USD"
    assert result.primary_account is True


def test_get_by_authorization_id_not_found(mock_get_for_product, mock_table):
    table_instance = mock_table
    table_instance.first.return_value = None
    svc = ProgramManagementAccountTable()

    with pytest.raises(AirtableRecordNotFoundError):
        svc.get_by_authorization_and_currency_id("AUT-1111-1111", "USD")
