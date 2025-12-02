import logging

from django.conf import settings
from mpt_extension_sdk.runtime.djapp.conf import get_for_product
from pyairtable import Table
from pyairtable.formulas import AND, EQUAL, FIELD, STR_VALUE

from swo_aws_extension.airtable.errors import AirtableRecordNotFoundError
from swo_aws_extension.airtable.models import PMAFields, PMARecord

logger = logging.getLogger(__name__)


class ProgramManagementAccountTable:
    """Airtable table for Program Management Accounts (PMA)."""

    def __init__(self):
        api_key = settings.EXTENSION_CONFIG["AIRTABLE_API_TOKEN"]
        base_id = get_for_product(settings, "AIRTABLE_BASES", settings.AWS_PRODUCT_ID)

        self._table_name = "Program Management Accounts"
        self._table = Table(api_key, base_id, self._table_name)

    def get_by_authorization_and_currency_id(self, auth_id: str, currency: str) -> PMARecord:
        """Get PMA Authorization record by Authorization ID and currency.

        Args:
            auth_id: The Authorization ID to search for.
            currency: The currency to match.

        Returns:
            PMARecord: The corresponding PMA Authorization record.

        Raises:
            AirtableRecordNotFoundError: If no record is found with the given values.
        """
        record = self._table.first(
            formula=AND(
                EQUAL(FIELD(PMAFields.AUTHORIZATION_ID.value), STR_VALUE(auth_id)),
                EQUAL(FIELD(PMAFields.CURRENCY.value), STR_VALUE(currency)),
                FIELD(PMAFields.PRIMARY_ACCOUNT.value),
            )
        )
        if not record:
            logger.info(
                "No record found in table %s with Authorization ID: %s",
                self._table_name,
                auth_id,
            )
            raise AirtableRecordNotFoundError(
                f"No record found with Authorization ID: {auth_id}",
            )
        return PMARecord.from_airtable_record(record)
