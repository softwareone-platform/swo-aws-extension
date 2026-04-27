import pytest

from swo_aws_extension.swo.service_provisioning.models import (
    ServiceContact,
    ServiceOnboardingRequest,
    ServiceOnboardingResponse,
)


@pytest.fixture
def sample_contact():
    return ServiceContact(
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        phone_number="+34666666666",
        language_code="EN",
    )


@pytest.fixture
def sample_request(sample_contact):
    return ServiceOnboardingRequest(
        erp_client_id="SWO_CH",
        contract_no="CH-CCO-331705",
        service_description="DWE",
        contacts=[sample_contact],
    )


def test_service_contact_to_api_dict_maps_all_fields(sample_contact):
    result = sample_contact.to_api_dict()

    assert result["firstName"] == "John"
    assert result["lastName"] == "Doe"
    assert result["email"] == "john.doe@example.com"
    assert result["phoneNumber"] == "+34666666666"
    assert result["languageCode"] == "EN"


def test_service_onboarding_request_to_api_dict_maps_top_level_fields(sample_request):
    result = sample_request.to_api_dict()

    assert result["erpClientId"] == "SWO_CH"
    assert result["contractNo"] == "CH-CCO-331705"
    assert result["serviceDescription"] == "DWE"


def test_service_onboarding_request_to_api_dict_serializes_contacts(sample_request, sample_contact):
    result = sample_request.to_api_dict()

    assert len(result["contacts"]) == 1
    assert result["contacts"][0] == sample_contact.to_api_dict()


def test_service_onboarding_request_to_api_dict_empty_contacts():
    request = ServiceOnboardingRequest(
        erp_client_id="SWO_CH",
        contract_no="CH-CCO-000",
        service_description="DWE",
        contacts=[],
    )

    result = request.to_api_dict()

    assert result["contacts"] == []


def test_service_onboarding_request_default_contacts_is_empty_list():
    request = ServiceOnboardingRequest(
        erp_client_id="SWO_CH",
        contract_no="CH-CCO-000",
        service_description="DWE",
    )

    result = request.contacts

    assert result == []


def test_service_onboarding_response_stores_erp_project_no():
    response = ServiceOnboardingResponse(erp_project_no="PRO-123-13-132")

    result = response.erp_project_no

    assert result == "PRO-123-13-132"
