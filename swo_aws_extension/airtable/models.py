import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Self

logger = logging.getLogger(__name__)


class PMAFields(StrEnum):
    """Fields in the Program Management Account Airtable table."""

    AUTHORIZATION_ID = "Authorization ID"
    PMA_ACCOUNT_ID = "PMA Account ID"
    PMA_ID = "PMA ID"
    PMA_NAME = "PMA Name"
    PMA_EMAIL = "PMA Email"
    CURRENCY = "Currency"
    COUNTRY = "Country"
    PRIMARY_ACCOUNT = "Primary Account"


@dataclass(frozen=True)
class PMARecord:
    """Represent the Program Management Account record from Airtable."""

    authorization_id: str | None
    pma_account_id: str | None
    pma_id: str | None
    pma_name: str | None
    pma_email: str | None
    currency: str | None
    country: str | None
    primary_account: bool

    @classmethod
    def from_airtable_record(cls, record: Any) -> Self:
        """Creates an instance from a raw Airtable record."""
        fields = record.get("fields", {})
        return cls(
            authorization_id=fields.get(PMAFields.AUTHORIZATION_ID),
            pma_account_id=fields.get(PMAFields.PMA_ACCOUNT_ID),
            pma_id=fields.get(PMAFields.PMA_ID),
            pma_name=fields.get(PMAFields.PMA_NAME),
            pma_email=fields.get(PMAFields.PMA_EMAIL),
            currency=fields.get(PMAFields.CURRENCY),
            country=fields.get(PMAFields.COUNTRY),
            primary_account=bool(fields.get(PMAFields.PRIMARY_ACCOUNT)),
        )
