from http import HTTPStatus

import pytest
import responses

from swo_aws_extension.swo.finops.client import FinOpsClient, get_ffc_client
from swo_aws_extension.swo.finops.errors import (
    FinOpsHttpError,
    FinOpsNotFoundError,
)

BASE_URL = "https://finops.test.com/"
API_TOKEN = "test-api-token"


@pytest.fixture
def finops_client():
    return FinOpsClient(BASE_URL, API_TOKEN)


@pytest.fixture
def mock_finops_api(requests_mocker):
    return requests_mocker


def test_init_with_trailing_slash():
    result = FinOpsClient("https://finops.test.com/", API_TOKEN)

    assert result.base_url == "https://finops.test.com/"


def test_init_without_trailing_slash():
    result = FinOpsClient("https://finops.test.com", API_TOKEN)

    assert result.base_url == "https://finops.test.com/"


def test_create_entitlement_success(finops_client, mock_finops_api):
    expected_response = {"id": "ENT-001", "status": "new"}
    mock_finops_api.add(
        responses.POST,
        f"{BASE_URL}entitlements",
        json=expected_response,
        status=HTTPStatus.CREATED,
    )

    result = finops_client.create_entitlement(
        affiliate_external_id="AFF-001",
        datasource_id="DS-001",
        name="AWS",
    )

    assert result == expected_response


def test_create_entitlement_http_error(finops_client, mock_finops_api):
    mock_finops_api.add(
        responses.POST,
        f"{BASE_URL}entitlements",
        json={"error": "Bad Request"},
        status=HTTPStatus.BAD_REQUEST,
    )

    with pytest.raises(FinOpsHttpError) as exc_info:
        finops_client.create_entitlement(
            affiliate_external_id="AFF-001",
            datasource_id="DS-001",
        )

    assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST


def test_get_entitlement_success(finops_client, mock_finops_api):
    expected_response = {"id": "FENT-2289-7693-2555", "status": "active"}
    mock_finops_api.add(
        responses.GET,
        f"{BASE_URL}entitlements/FENT-2289-7693-2555",
        json=expected_response,
        status=HTTPStatus.OK,
    )

    result = finops_client.get_entitlement("FENT-2289-7693-2555")

    assert result == expected_response


def test_get_entitlement_not_found(finops_client, mock_finops_api):
    mock_finops_api.add(
        responses.GET,
        f"{BASE_URL}entitlements/FENT-0000-0000-0000",
        json={"error": "Not Found"},
        status=HTTPStatus.NOT_FOUND,
    )

    with pytest.raises(FinOpsNotFoundError):
        finops_client.get_entitlement("FENT-0000-0000-0000")


def test_delete_entitlement_success(finops_client, mock_finops_api):
    mock_finops_api.add(
        responses.DELETE,
        f"{BASE_URL}entitlements/ENT-001",
        status=HTTPStatus.NO_CONTENT,
    )

    finops_client.delete_entitlement("ENT-001")  # act

    assert mock_finops_api.assert_call_count(f"{BASE_URL}entitlements/ENT-001", 1) is True


def test_delete_entitlement_not_found(finops_client, mock_finops_api):
    mock_finops_api.add(
        responses.DELETE,
        f"{BASE_URL}entitlements/ENT-001",
        json={"error": "Not Found"},
        status=HTTPStatus.NOT_FOUND,
    )

    with pytest.raises(FinOpsNotFoundError):
        finops_client.delete_entitlement("ENT-001")


def test_terminate_entitlement_success(finops_client, mock_finops_api):
    expected_response = {"id": "ENT-001", "status": "terminated"}
    mock_finops_api.add(
        responses.POST,
        f"{BASE_URL}entitlements/ENT-001/terminate",
        json=expected_response,
        status=HTTPStatus.OK,
    )

    result = finops_client.terminate_entitlement("ENT-001")

    assert result == expected_response


def test_terminate_entitlement_not_found(finops_client, mock_finops_api):
    mock_finops_api.add(
        responses.POST,
        f"{BASE_URL}entitlements/ENT-001/terminate",
        json={"error": "Not Found"},
        status=HTTPStatus.NOT_FOUND,
    )

    with pytest.raises(FinOpsNotFoundError):
        finops_client.terminate_entitlement("ENT-001")


def test_get_entitlement_by_datasource_found(finops_client, mock_finops_api):
    expected_entitlement = {"id": "ENT-001", "status": "active"}
    mock_finops_api.add(
        responses.GET,
        f"{BASE_URL}entitlements?datasource_id=DS-001&limit=1",
        json={"items": [expected_entitlement], "total": 1},
        status=HTTPStatus.OK,
    )

    result = finops_client.get_entitlement_by_datasource("DS-001")

    assert result == expected_entitlement


def test_get_entitlement_by_datasource_not_found(finops_client, mock_finops_api):
    mock_finops_api.add(
        responses.GET,
        f"{BASE_URL}entitlements?datasource_id=DS-001&limit=1",
        json={"items": [], "total": 0},
        status=HTTPStatus.OK,
    )

    result = finops_client.get_entitlement_by_datasource("DS-001")

    assert result is None


def test_get_entitlement_by_datasource_http_error(finops_client, mock_finops_api):
    mock_finops_api.add(
        responses.GET,
        f"{BASE_URL}entitlements?datasource_id=DS-001&limit=1",
        json={"error": "Internal Server Error"},
        status=HTTPStatus.INTERNAL_SERVER_ERROR,
    )

    with pytest.raises(FinOpsHttpError) as exc_info:
        finops_client.get_entitlement_by_datasource("DS-001")

    assert exc_info.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


def test_authorization_header_uses_api_token(finops_client, mock_finops_api):
    mock_finops_api.add(
        responses.GET,
        f"{BASE_URL}entitlements?datasource_id=DS-001&limit=1",
        json={"items": [], "total": 0},
        status=HTTPStatus.OK,
    )

    finops_client.get_entitlement_by_datasource("DS-001")  # act

    sent_request = mock_finops_api.calls[0].request
    request_headers = sent_request.headers
    assert request_headers["Authorization"] == f"Bearer {API_TOKEN}"
    assert request_headers["Accept"] == "application/json"
    assert request_headers["Content-Type"] == "application/json"


def test_request_id_header_is_unique_per_request(finops_client, mock_finops_api):
    mock_finops_api.add(
        responses.GET,
        f"{BASE_URL}entitlements?datasource_id=DS-001&limit=1",
        json={"items": [], "total": 0},
        status=HTTPStatus.OK,
    )
    mock_finops_api.add(
        responses.GET,
        f"{BASE_URL}entitlements?datasource_id=DS-002&limit=1",
        json={"items": [], "total": 0},
        status=HTTPStatus.OK,
    )
    finops_client.get_entitlement_by_datasource("DS-001")

    finops_client.get_entitlement_by_datasource("DS-002")  # act

    first_request, second_request = (call.request for call in mock_finops_api.calls)
    first_request_id = first_request.headers["X-Request-Id"]
    second_request_id = second_request.headers["X-Request-Id"]
    assert first_request_id
    assert first_request_id != second_request_id


def test_get_ffc_client_returns_singleton(ffc_client_settings, mocker):
    mocker.patch(
        "swo_aws_extension.swo.finops.client._FinOpsClientFactory._instance",
        None,
    )
    first_client = get_ffc_client()

    second_client = get_ffc_client()  # act

    assert first_client is second_client


def test_get_ffc_client_creates_from_settings(ffc_client_settings, mocker):
    mocker.patch(
        "swo_aws_extension.swo.finops.client._FinOpsClientFactory._instance",
        None,
    )

    result = get_ffc_client()  # act

    assert result is not None
    assert result.base_url == "https://local.local/ops/v1/"
    assert result.headers["Authorization"] == f"Bearer {ffc_client_settings.MPT_API_TOKEN}"
