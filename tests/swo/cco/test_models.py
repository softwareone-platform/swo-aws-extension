import datetime as dt

import pytest

from swo_aws_extension.swo.cco.models import CcoContract, CreateCcoRequest, CreateCcoResponse

FULL_REQUEST_START_DATE = dt.datetime.fromisoformat("2024-02-27T14:03:37+00:00")
DEFAULT_REQUEST_START_DATE = dt.datetime.fromisoformat("2024-01-01T00:00:00+00:00")


@pytest.fixture
def full_request():
    return CreateCcoRequest(
        software_one_legal_entity="SWO_CH",
        contract_number_reference="60114e35-4283-46b4-9bce-5b29cc486062",
        customer_number="CH-SCU-171523",
        enrollment_number="AGR-2119-4550-9999",
        manufacturer_code="SWOTS",
        start_date=FULL_REQUEST_START_DATE,
        currency_code="EUR",
        license_model="CAW-0046",
        customer_reference="Test1",
        contract_category="CLOUD-BASI",
    )


@pytest.fixture
def full_contract_dict():
    return {
        "contractNumber": "CH-CCO-331705",
        "enrollmentNumber": "AGR-2119-4550-9999",
        "referenceNumber": "REF-001",
        "deleted": True,
        "disabled": True,
        "contractNumberReference": "60114e35-4283-46b4-9bce-5b29cc486062",
        "masterAgreementNumber": "AGR-2119-4550-9999",
    }


def test_create_cco_request_to_api_dict_maps_all_fields(full_request):
    result = full_request.to_api_dict()

    assert result == {
        "softwareOneLegalEntity": "SWO_CH",
        "contractNumberReference": "60114e35-4283-46b4-9bce-5b29cc486062",
        "customerNumber": "CH-SCU-171523",
        "customerReference": "Test1",
        "enrollmentNumber": "AGR-2119-4550-9999",
        "manufacturerCode": "SWOTS",
        "startDate": "2024-02-27T14:03:37+00:00",
        "currencyCode": "EUR",
        "licenseModel": "CAW-0046",
        "contractCategory": "CLOUD-BASI",
    }


def test_create_cco_request_default_customer_reference():
    request = CreateCcoRequest(
        software_one_legal_entity="SWO_CH",
        contract_number_reference="ref",
        customer_number="CH-SCU-000",
        enrollment_number="AGR-0000",
        manufacturer_code="SWOTS",
        start_date=DEFAULT_REQUEST_START_DATE,
        currency_code="EUR",
        license_model="CAW-0046",
    )

    result = request.to_api_dict()

    assert not result["customerReference"]


def test_create_cco_request_default_contract_category():
    request = CreateCcoRequest(
        software_one_legal_entity="SWO_CH",
        contract_number_reference="ref",
        customer_number="CH-SCU-000",
        enrollment_number="AGR-0000",
        manufacturer_code="SWOTS",
        start_date=DEFAULT_REQUEST_START_DATE,
        currency_code="EUR",
        license_model="CAW-0046",
    )

    result = request.to_api_dict()

    assert result["contractCategory"] == "CLOUD-BASI"


def test_create_cco_response_stores_contract_number():
    response = CreateCcoResponse(contract_number="CH-CCO-331705")

    result = response.contract_number

    assert result == "CH-CCO-331705"


def test_cco_contract_from_dict_maps_all_fields(full_contract_dict):
    result = CcoContract.from_dict(full_contract_dict)

    assert result == CcoContract(
        contract_number="CH-CCO-331705",
        enrollment_number="AGR-2119-4550-9999",
        reference_number="REF-001",
        deleted=True,
        disabled=True,
        contract_number_reference="60114e35-4283-46b4-9bce-5b29cc486062",
        master_agreement_number="AGR-2119-4550-9999",
    )


def test_cco_contract_from_dict_optional_fields_default_to_none():
    result = CcoContract.from_dict({"contractNumber": "CH-CCO-000"})

    assert result.enrollment_number is None
    assert result.reference_number is None
    assert result.contract_number_reference is None
    assert result.master_agreement_number is None


def test_cco_contract_from_dict_bool_fields_default_to_false():
    result = CcoContract.from_dict({"contractNumber": "CH-CCO-000"})

    assert result.deleted is False
    assert result.disabled is False
