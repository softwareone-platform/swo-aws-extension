from dataclasses import dataclass, field


@dataclass
class ServiceContact:
    """A contact to onboard into ServiceNow."""

    first_name: str
    last_name: str
    email: str
    phone_number: str
    language_code: str

    def to_api_dict(self) -> dict:
        """Serialize to API payload."""
        return {
            "firstName": self.first_name,
            "lastName": self.last_name,
            "email": self.email,
            "phoneNumber": self.phone_number,
            "languageCode": self.language_code,
        }


@dataclass
class ServiceOnboardingRequest:
    """Input data to onboard a CCO in Services Provisioning."""

    erp_client_id: str
    contract_no: str
    service_description: str
    contacts: list[ServiceContact] = field(default_factory=list)

    def to_api_dict(self) -> dict:
        """Serialize to API payload."""
        return {
            "erpClientId": self.erp_client_id,
            "contractNo": self.contract_no,
            "serviceDescription": self.service_description,
            "contacts": [contact.to_api_dict() for contact in self.contacts],
        }


@dataclass
class ServiceOnboardingResponse:
    """Result of a successful service onboarding."""

    erp_project_no: str
