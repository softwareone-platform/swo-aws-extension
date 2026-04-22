import datetime as dt
from http import HTTPStatus

import pytest
import requests
import responses

from swo_aws_extension.swo.cco.client import (
    CcoClient,
    _CcoClientFactory,  # noqa: PLC2701
    get_cco_client,
)
from swo_aws_extension.swo.cco.errors import CcoError, CcoHttpError, CcoNotFoundError
from swo_aws_extension.swo.cco.models import CcoContract, CreateCcoRequest

CCO_BASE_URL = "https://swo-procops-app-externalapi-contracts-test.azurewebsites.net/"
MODULE = "swo_aws_extension.swo.cco.client"
SAMPLE_START_DATE = dt.datetime.fromisoformat("2024-02-27T14:03:37+00:00")
SAMPLE_START_DATE_SHORT = dt.datetime.fromisoformat("2024-02-27T00:00:00+00:00")
ERROR_START_DATE = dt.datetime.fromisoformat("2024-01-01T00:00:00+00:00")


class _LockThatSetsInstance:
    """Test helper: simulates a lock that sets _CcoClientFactory._instance on enter."""

    def __init__(self, instance):
        self._instance = instance

    def __enter__(self):
        _CcoClientFactory._instance = self._instance  # noqa: SLF001
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture
def mock_oauth_token(requests_mocker, config):
    requests_mocker.add(
        responses.POST,
        config.cco_oauth_url,
        json={"access_token": "test-token", "expires_in": 3600},
        status=HTTPStatus.OK,
    )
    return requests_mocker


@pytest.fixture
def cco_client(config):
    return CcoClient(config)


@pytest.fixture
def mock_cco_api(mock_oauth_token, requests_mocker):
    """HTTP mock for CCO API.

    Depends on mock_oauth_token to ensure get_auth_token
    is patched before responses.RequestsMock intercepts any HTTP traffic.
    """
    return requests_mocker


@pytest.fixture
def sample_request():
    return CreateCcoRequest(
        software_one_legal_entity="SWO_CH",
        contract_number_reference="60114e35-4283-46b4-9bce-5b29cc486062",
        customer_number="CH-SCU-171523",
        enrollment_number="AGR-2119-4550-9999",
        manufacturer_code="SWOTS",
        start_date=SAMPLE_START_DATE,
        currency_code="EUR",
        license_model="CAW-0046",
        customer_reference="Test1",
    )


@pytest.fixture
def create_cco_response_body():
    return {
        "contractInsert": {
            "contractNumber": "CH-CCO-331705",
            "enrollmentNumber": "AGR-2119-4550-9999",
            "referenceNumber": None,
            "deleted": False,
            "disabled": False,
            "contractNumberReference": "AGR-2119-4550-9999",
            "masterAgreementNumber": "AGR-2119-4550-9999",
        }
    }


@pytest.fixture
def contract_list_body():
    return [
        {
            "contractNumber": "CH-CCO-331705",
            "enrollmentNumber": "AGR-2119-4550-9999",
            "referenceNumber": None,
            "deleted": False,
            "disabled": False,
            "contractNumberReference": "60114e35-4283-46b4-9bce-5b29cc486062",
            "masterAgreementNumber": "AGR-2119-4550-9999",
        }
    ]


def test_create_cco_success(cco_client, mock_cco_api, create_cco_response_body):
    mock_cco_api.add(
        responses.POST,
        f"{CCO_BASE_URL}v1/contracts",
        json=create_cco_response_body,
        status=HTTPStatus.OK,
    )

    result = cco_client.create_cco(
        CreateCcoRequest(
            software_one_legal_entity="SWO_CH",
            contract_number_reference="60114e35-4283-46b4-9bce-5b29cc486062",
            customer_number="CH-SCU-171523",
            enrollment_number="AGR-2119-4550-9999",
            manufacturer_code="SWOTS",
            start_date=SAMPLE_START_DATE_SHORT,
            currency_code="EUR",
            license_model="CAW-0046",
        )
    )

    assert result.contract_number == "CH-CCO-331705"


def test_create_cco_http_error(cco_client, mock_cco_api):
    mock_cco_api.add(
        responses.POST,
        f"{CCO_BASE_URL}v1/contracts",
        json={"error": "Bad Request"},
        status=HTTPStatus.BAD_REQUEST,
    )

    with pytest.raises(CcoHttpError) as exc_info:
        cco_client.create_cco(
            CreateCcoRequest(
                software_one_legal_entity="SWO_CH",
                contract_number_reference="tenant-id",
                customer_number="CH-SCU-000",
                enrollment_number="AGR-0000",
                manufacturer_code="SWOTS",
                start_date=ERROR_START_DATE,
                currency_code="EUR",
                license_model="MP",
            )
        )

    assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST


def test_get_all_contracts_success(cco_client, mock_cco_api, contract_list_body):
    mock_cco_api.add(
        responses.GET,
        f"{CCO_BASE_URL}v1/contracts/all/60114e35-4283-46b4-9bce-5b29cc486062",
        json=contract_list_body,
        status=HTTPStatus.OK,
    )

    result = cco_client.get_all_contracts("60114e35-4283-46b4-9bce-5b29cc486062")

    assert len(result) == 1
    assert isinstance(result[0], CcoContract)
    assert result[0].contract_number == "CH-CCO-331705"


def test_get_all_contracts_http_error(cco_client, mock_cco_api):
    mock_cco_api.add(
        responses.GET,
        f"{CCO_BASE_URL}v1/contracts/all/tenant-id",
        json={"error": "Server Error"},
        status=HTTPStatus.INTERNAL_SERVER_ERROR,
    )

    with pytest.raises(CcoHttpError) as exc_info:
        cco_client.get_all_contracts("tenant-id")

    assert exc_info.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


def test_get_contract_by_id_found(cco_client, mock_cco_api):
    mock_cco_api.add(
        responses.GET,
        f"{CCO_BASE_URL}v1/contracts/CH-CCO-331705",
        json={
            "contractNumber": "CH-CCO-331705",
            "enrollmentNumber": "AGR-2119-4550-9999",
            "referenceNumber": None,
            "deleted": False,
            "disabled": False,
            "contractNumberReference": "60114e35",
            "masterAgreementNumber": "AGR-2119-4550-9999",
        },
        status=HTTPStatus.OK,
    )

    result = cco_client.get_contract_by_id("CH-CCO-331705")

    assert result is not None
    assert result.contract_number == "CH-CCO-331705"


def test_get_contract_by_id_not_found(cco_client, mock_cco_api):
    mock_cco_api.add(
        responses.GET,
        f"{CCO_BASE_URL}v1/contracts/CH-CCO-XXXX",
        json={},
        status=HTTPStatus.NOT_FOUND,
    )

    result = cco_client.get_contract_by_id("CH-CCO-XXXX")

    assert result is None


def test_get_contract_by_id_http_error(cco_client, mock_cco_api):
    mock_cco_api.add(
        responses.GET,
        f"{CCO_BASE_URL}v1/contracts/CH-CCO-331705",
        json={"error": "Server Error"},
        status=HTTPStatus.INTERNAL_SERVER_ERROR,
    )

    with pytest.raises(CcoHttpError) as exc_info:
        cco_client.get_contract_by_id("CH-CCO-331705")

    assert exc_info.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


@pytest.mark.parametrize(
    "malformed_body",
    [
        [],
        "unexpected string",
        42,
        {},
    ],
)
def test_get_contract_by_id_malformed_response_raises_cco_error(
    cco_client, mock_cco_api, malformed_body
):
    mock_cco_api.add(
        responses.GET,
        f"{CCO_BASE_URL}v1/contracts/CH-CCO-BAD",
        json=malformed_body,
        status=HTTPStatus.OK,
    )

    with pytest.raises(CcoError) as exc_info:
        cco_client.get_contract_by_id("CH-CCO-BAD")

    assert "CH-CCO-BAD" in str(exc_info.value)


def test_get_cco_client_singleton(mocker):
    mocker.patch(
        f"{MODULE}._CcoClientFactory._instance",
        None,
    )

    result = get_cco_client()

    second = get_cco_client()
    assert result is second


def test_create_cco_request_to_api_dict_serializes_correctly(sample_request):
    result = sample_request.to_api_dict()  # act

    assert result["softwareOneLegalEntity"] == "SWO_CH"
    assert result["enrollmentNumber"] == "AGR-2119-4550-9999"
    assert result["contractCategory"] == "CLOUD-BASI"
    assert "startDate" in result


def test_get_all_contracts_not_found(cco_client, mock_cco_api):
    mock_cco_api.add(
        responses.GET,
        f"{CCO_BASE_URL}v1/contracts/all/unknown-id",
        json={"error": "Not Found"},
        status=HTTPStatus.NOT_FOUND,
    )

    with pytest.raises(CcoNotFoundError):
        cco_client.get_all_contracts("unknown-id")  # act


@pytest.mark.parametrize(
    "malformed_body",
    [
        {},
        {"contractInsert": None},
        {"contractInsert": {}},
        {"contractInsert": {"enrollmentNumber": "X"}},
        [],
        "unexpected string",
        {"contractInsert": {"contractNumber": ""}},
        {"contractInsert": {"contractNumber": "   "}},
        {"contractInsert": {"contractNumber": None}},
    ],
)
def test_create_cco_malformed_response_raises_cco_error(
    cco_client, mock_cco_api, malformed_body, sample_request
):
    mock_cco_api.add(
        responses.POST,
        f"{CCO_BASE_URL}v1/contracts",
        json=malformed_body,
        status=HTTPStatus.OK,
    )

    with pytest.raises(CcoError):
        cco_client.create_cco(sample_request)


@pytest.mark.parametrize(
    "malformed_body",
    [
        {},
        {"contractNumber": "X"},
        "unexpected string",
        42,
        [{}],
        [{"enrollmentNumber": "X"}],
    ],
)
def test_get_all_contracts_malformed_response_raises_cco_error(
    cco_client, mock_cco_api, malformed_body
):
    mock_cco_api.add(
        responses.GET,
        f"{CCO_BASE_URL}v1/contracts/all/mpa-id",
        json=malformed_body,
        status=HTTPStatus.OK,
    )

    with pytest.raises(CcoError) as exc_info:
        cco_client.get_all_contracts("mpa-id")

    assert "mpa-id" in str(exc_info.value)


def test_create_cco_plain_text_response_raises_cco_error(cco_client, mock_cco_api, sample_request):
    mock_cco_api.add(
        responses.POST,
        f"{CCO_BASE_URL}v1/contracts",
        body="OK",
        status=HTTPStatus.OK,
    )

    with pytest.raises(CcoError):
        cco_client.create_cco(sample_request)


def test_get_all_contracts_plain_text_response_raises_cco_error(cco_client, mock_cco_api):
    mock_cco_api.add(
        responses.GET,
        f"{CCO_BASE_URL}v1/contracts/all/mpa-id",
        body="OK",
        status=HTTPStatus.OK,
    )

    with pytest.raises(CcoError) as exc_info:
        cco_client.get_all_contracts("mpa-id")

    assert "mpa-id" in str(exc_info.value)


def test_get_contract_by_id_plain_text_response_raises_cco_error(cco_client, mock_cco_api):
    mock_cco_api.add(
        responses.GET,
        f"{CCO_BASE_URL}v1/contracts/CH-CCO-TXT",
        body="OK",
        status=HTTPStatus.OK,
    )

    with pytest.raises(CcoError) as exc_info:
        cco_client.get_contract_by_id("CH-CCO-TXT")

    assert "CH-CCO-TXT" in str(exc_info.value)


def test_get_cco_client_factory_inner_check_skips_when_already_set(mocker):
    """Cover the double-check branch: inner check sees instance already set."""
    mock_instance = mocker.MagicMock(spec=CcoClient)
    mocker.patch.object(_CcoClientFactory, "_instance", None)
    mocker.patch.object(_CcoClientFactory, "_init_lock", _LockThatSetsInstance(mock_instance))

    result = _CcoClientFactory.get_client()

    assert result is mock_instance


def test_wrap_http_error_none_response_raises_cco_http_error(cco_client, mocker):
    mocker.patch.object(
        cco_client,
        "post",
        side_effect=requests.HTTPError("connection error"),
    )

    with pytest.raises(CcoHttpError) as exc_info:
        cco_client.create_cco(mocker.MagicMock())

    assert exc_info.value.status_code == 0


def test_get_contract_by_id_http_error_none_response(cco_client, mocker):
    mock_response = mocker.MagicMock()
    mock_response.status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    mock_response.raise_for_status.side_effect = requests.HTTPError("connection error")
    mocker.patch.object(cco_client, "get", return_value=mock_response)

    with pytest.raises(CcoHttpError) as exc_info:
        cco_client.get_contract_by_id("CH-CCO-999")

    assert exc_info.value.status_code == 0
