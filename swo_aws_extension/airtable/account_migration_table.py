from django.conf import settings
from pyairtable import Api
from pyairtable.formulas import EQ, Field

from swo_aws_extension.airtable.models import (
    AccountMigrationFields,
    AccountMigrationRecord,
    AccountMigrationStatus,
)


class AwsAccountMigrationTable:
    """Airtable table for the AWS accounts to migrate.

    The table lives in its own Airtable base, configured through
    ``EXTENSION_CONFIG["AIRTABLE_ACCOUNT_MIGRATION_BASE_ID"]``.
    """

    def __init__(self):
        api_key = settings.EXTENSION_CONFIG["AIRTABLE_API_TOKEN"]
        api = Api(api_key)

        base_id = settings.EXTENSION_CONFIG["AIRTABLE_ACCOUNT_MIGRATION_BASE_ID"]
        self._table_name = "AWS Account Migration"
        self._table = api.table(base_id, self._table_name)

    def get_by_status(self, status: AccountMigrationStatus) -> list[AccountMigrationRecord]:
        """Get the records with the given migration status, in table order."""
        return self._get_all_by_field(AccountMigrationFields.MIGRATION_STATUS, status)

    def get_by_order_id(self, order_id: str) -> AccountMigrationRecord | None:
        """Get the record linked to a Marketplace order id, if any."""
        records = self._get_all_by_field(AccountMigrationFields.MPT_ORDER_ID, order_id)
        return records[0] if records else None

    def get_by_billing_transfer_start_date(self, start_date: str) -> list[AccountMigrationRecord]:
        """Get the records whose billing transfer starts on the given ISO date (YYYY-MM-DD)."""
        return self._get_all_by_field(
            AccountMigrationFields.BILLING_TRANSFER_START_DATE, start_date
        )

    def save(self, record: AccountMigrationRecord) -> AccountMigrationRecord:
        """Save a record to Airtable (create or update)."""
        fields = record.to_airtable_fields()
        if record.is_new():
            result = self._table.create(fields)
        else:
            result = self._table.update(record.record_id, fields)
        return AccountMigrationRecord.from_airtable_record(result)

    def update_status(
        self,
        record: AccountMigrationRecord,
        status: AccountMigrationStatus,
        error: str | None = None,
    ) -> AccountMigrationRecord:
        """Update the migration status of a record, optionally with the error detail."""
        record.migration_status = status
        if error is not None:
            record.error = error
        return self.save(record)

    def _get_all_by_field(
        self, field_name: AccountMigrationFields, field_value: str
    ) -> list[AccountMigrationRecord]:
        formula = EQ(Field(field_name.value), str(field_value))
        records = self._table.all(formula=formula)
        return [AccountMigrationRecord.from_airtable_record(record) for record in records]
