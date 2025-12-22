import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Self

logger = logging.getLogger(__name__)


class OpScaleFields(StrEnum):
    """Fields in the OpScale Airtable table."""

    ACCOUNT_ID = "Account ID"
    BUYER_ID = "Buyer ID"
    AGREEMENT_ID = "Agreement ID"
    STATUS = "Status"
    CREATED = "Created"
    LAST_USAGE_DATE = "Last Usage Date"


@dataclass
class OpScaleRecord:
    """Represent the OpScale record from Airtable."""

    account_id: str | None = None
    buyer_id: str | None = None
    agreement_id: str | None = None
    status: str | None = None
    last_usage_date: str | None = None
    record_id: str | None = field(default=None, repr=False)

    @classmethod
    def from_airtable_record(cls, record: Any) -> Self:
        """Creates an instance from a raw Airtable record."""
        fields = record.get("fields", {})
        return cls(
            record_id=record.get("id"),
            account_id=fields.get(OpScaleFields.ACCOUNT_ID),
            buyer_id=fields.get(OpScaleFields.BUYER_ID),
            agreement_id=fields.get(OpScaleFields.AGREEMENT_ID),
            status=fields.get(OpScaleFields.STATUS),
            last_usage_date=fields.get(OpScaleFields.LAST_USAGE_DATE),
        )

    def to_airtable_fields(self) -> dict[str, Any]:
        """Convert the record to Airtable fields format."""
        fields = {}
        if self.account_id is not None:
            fields[OpScaleFields.ACCOUNT_ID] = self.account_id
        if self.buyer_id is not None:
            fields[OpScaleFields.BUYER_ID] = self.buyer_id
        if self.agreement_id is not None:
            fields[OpScaleFields.AGREEMENT_ID] = self.agreement_id
        if self.status is not None:
            fields[OpScaleFields.STATUS] = self.status
        if self.last_usage_date is not None:
            fields[OpScaleFields.LAST_USAGE_DATE] = self.last_usage_date
        return fields

    def is_new(self) -> bool:
        """Check if the record is new (not yet saved to Airtable)."""
        return self.record_id is None
