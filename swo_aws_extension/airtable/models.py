from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Self


class FinOpsFields(StrEnum):
    """Fields in the FinOps Airtable table."""

    ACCOUNT_ID = "Account ID"
    BUYER_ID = "Buyer ID"
    AGREEMENT_ID = "Agreement ID"
    STATUS = "Status"
    ENTITLEMENT_ID = "Entitlement ID"
    CREATED = "Created"
    LAST_USAGE_DATE = "Last Usage Date"


@dataclass
class FinOpsRecord:
    """Represent the FinOps record from Airtable."""

    account_id: str
    buyer_id: str
    agreement_id: str
    entitlement_id: str
    status: str
    last_usage_date: str
    record_id: str | None = field(default=None, repr=False)

    @classmethod
    def from_airtable_record(cls, record: Any) -> Self:
        """Creates an instance from a raw Airtable record."""
        fields = record.get("fields", {})
        return cls(
            record_id=record.get("id"),
            account_id=fields.get(FinOpsFields.ACCOUNT_ID),
            buyer_id=fields.get(FinOpsFields.BUYER_ID),
            agreement_id=fields.get(FinOpsFields.AGREEMENT_ID),
            entitlement_id=fields.get(FinOpsFields.ENTITLEMENT_ID),
            status=fields.get(FinOpsFields.STATUS),
            last_usage_date=fields.get(FinOpsFields.LAST_USAGE_DATE),
        )

    def to_airtable_fields(self) -> dict[str, Any]:
        """Convert the record to Airtable fields format."""
        field_mapping = {
            FinOpsFields.ACCOUNT_ID: self.account_id,
            FinOpsFields.BUYER_ID: self.buyer_id,
            FinOpsFields.AGREEMENT_ID: self.agreement_id,
            FinOpsFields.ENTITLEMENT_ID: self.entitlement_id,
            FinOpsFields.STATUS: self.status,
            FinOpsFields.LAST_USAGE_DATE: self.last_usage_date,
        }
        return {key: item_data for key, item_data in field_mapping.items() if item_data is not None}

    def is_new(self) -> bool:
        """Check if the record is new (not yet saved to Airtable)."""
        return self.record_id is None
