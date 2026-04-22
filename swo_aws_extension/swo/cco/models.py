import datetime as dt
from dataclasses import dataclass
from typing import Any


@dataclass
class CreateCcoRequest:
    """Input data to create a CCO contract in Navision."""

    software_one_legal_entity: str
    contract_number_reference: str
    customer_number: str
    enrollment_number: str
    manufacturer_code: str
    start_date: dt.datetime
    currency_code: str
    license_model: str
    customer_reference: str = ""
    contract_category: str = "CLOUD-BASI"

    def to_api_dict(self) -> dict[str, str]:
        """Serialize to CCO API payload."""
        return {
            "softwareOneLegalEntity": self.software_one_legal_entity,
            "contractNumberReference": self.contract_number_reference,
            "customerNumber": self.customer_number,
            "customerReference": self.customer_reference,
            "enrollmentNumber": self.enrollment_number,
            "manufacturerCode": self.manufacturer_code,
            "startDate": self.start_date.isoformat(),
            "currencyCode": self.currency_code,
            "licenseModel": self.license_model,
            "contractCategory": self.contract_category,
        }


@dataclass
class CreateCcoResponse:
    """Result of a successful CCO contract creation."""

    contract_number: str


@dataclass
class CcoContract:
    """Domain representation of a CCO contract."""

    contract_number: str
    enrollment_number: str | None = None
    reference_number: str | None = None
    deleted: bool = False
    disabled: bool = False
    contract_number_reference: str | None = None
    master_agreement_number: str | None = None

    @classmethod
    def from_dict(cls, raw_data: dict[str, Any]) -> "CcoContract":
        """Build a CcoContract from a raw API response dict."""
        return cls(
            contract_number=raw_data.get("contractNumber", ""),
            enrollment_number=raw_data.get("enrollmentNumber"),
            reference_number=raw_data.get("referenceNumber"),
            deleted=raw_data.get("deleted", False),
            disabled=raw_data.get("disabled", False),
            contract_number_reference=raw_data.get("contractNumberReference"),
            master_agreement_number=raw_data.get("masterAgreementNumber"),
        )
