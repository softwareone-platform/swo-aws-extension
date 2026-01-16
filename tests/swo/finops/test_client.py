from http import HTTPStatus

import pytest
import responses

from swo_aws_extension.swo.finops.client import FinOpsClient, get_ffc_client
from swo_aws_extension.swo.finops.errors import (
    FinOpsHttpError,
    FinOpsNotFoundError,
)

BASE_URL = "https://finops.test.com/"
SUB = "test-sub"
SECRET = "test-secret"


@pytest.fixture
def finops_client():
    return FinOpsClient(BASE_URL, SUB, SECRET)


@pytest.fixture
def mock_finops_api(requests_mocker):
    return requests_mocker


def test_init_with_trailing_slash():
    result = FinOpsClient("https://finops.test.com/", SUB, SECRET)

    assert result.base_url == "https://finops.test.com/"


def test_init_without_trailing_slash():
    result = FinOpsClient("https://finops.test.com", SUB, SECRET)

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


def test_token_is_refreshed_on_first_request(finops_client, mock_finops_api):
    mock_finops_api.add(
        responses.GET,
        f"{BASE_URL}entitlements?datasource_id=DS-001&limit=1",
        json={"items": [], "total": 0},
        status=HTTPStatus.OK,
    )

    finops_client.get_entitlement_by_datasource("DS-001")  # act

    assert "Authorization" in finops_client.headers


def test_authorization_header_is_set(finops_client, mock_finops_api):
    mock_finops_api.add(
        responses.GET,
        f"{BASE_URL}entitlements?datasource_id=DS-001&limit=1",
        json={"items": [], "total": 0},
        status=HTTPStatus.OK,
    )

    finops_client.get_entitlement_by_datasource("DS-001")  # act

    assert "Authorization" in finops_client.headers
    assert finops_client.headers["Authorization"].startswith("Bearer ")


def test_token_not_refreshed_when_valid(finops_client, mock_finops_api):
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
    first_token = finops_client.headers["Authorization"]

    finops_client.get_entitlement_by_datasource("DS-002")  # act

    second_token = finops_client.headers["Authorization"]
    assert first_token == second_token


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
    assert result.base_url == "https://local.local/"
