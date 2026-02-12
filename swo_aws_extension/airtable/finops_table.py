from django.conf import settings
from mpt_extension_sdk.runtime.djapp.conf import get_for_product
from pyairtable import Api
from pyairtable.formulas import EQ, Field

from swo_aws_extension.airtable.models import FinOpsFields, FinOpsRecord


class FinOpsEntitlementsTable:
    """Airtable table for FinOps Entitlements."""

    def __init__(self):
        api_key = settings.EXTENSION_CONFIG["AIRTABLE_API_TOKEN"]
        api = Api(api_key)

        base_id = get_for_product(settings, "AIRTABLE_BASES", settings.AWS_PRODUCT_ID)
        self._table_name = "FinOps Entitlements"
        self._table = api.table(base_id, self._table_name)

    def get_by_agreement_id(self, agreement_id: str) -> list[FinOpsRecord]:
        """Get list of record by agreement id."""
        records = self._table.all(
            formula=EQ(Field(FinOpsFields.AGREEMENT_ID.value), str(agreement_id))
        )
        if not records:
            return []
        return [FinOpsRecord.from_airtable_record(record) for record in records]

    def save(self, record: FinOpsRecord) -> FinOpsRecord:
        """Save a record to Airtable (create or update)."""
        fields = record.to_airtable_fields()
        if record.is_new():
            result = self._table.create(fields)
        else:
            result = self._table.update(record.record_id, fields)
        return FinOpsRecord.from_airtable_record(result)

    def update_status_and_usage_date(
        self, record: FinOpsRecord, status: str, last_usage_date: str
    ) -> FinOpsRecord:
        """Update status and last_usage_date for a record."""
        record.status = status
        record.last_usage_date = last_usage_date
        return self.save(record)
