from http import HTTPStatus

import pytest
import responses

from swo_aws_extension.swo.crm_service.client import (
    CRMServiceClient,
    ServiceRequest,
    get_service_client,
)
from swo_aws_extension.swo.crm_service.errors import (
    CRMHttpError,
    CRMNotFoundError,
)

BASE_URL = "https://crm.test.com/"


@pytest.fixture
def crm_client(config):
    return CRMServiceClient(config)


@pytest.fixture
def mock_crm_api(requests_mocker):
    return requests_mocker


@pytest.fixture
def mock_oauth_token(mocker):
    return mocker.patch(
        "swo_aws_extension.swo.crm_service.client.get_auth_token",
        return_value={"access_token": "test-token", "expires_in": 3600},
    )


def test_init_with_trailing_slash(settings, config):
    settings.EXTENSION_CONFIG["CRM_API_BASE_URL"] = "https://crm.test.com/"

    result = CRMServiceClient(config)

    assert result.base_url == "https://crm.test.com/"


def test_init_without_trailing_slash(settings, config):
    settings.EXTENSION_CONFIG["CRM_API_BASE_URL"] = "https://crm.test.com"

    result = CRMServiceClient(config)

    assert result.base_url == "https://crm.test.com/"


def test_init_sets_api_version(settings, config):
    result = CRMServiceClient(config, api_version="2.0.0")

    assert result.api_version == "2.0.0"


def test_init_default_api_version(settings, config):
    result = CRMServiceClient(config)

    assert result.api_version == "3.0.0"


def test_create_service_request_success(crm_client, mock_crm_api, mock_oauth_token):
    expected_response = {"id": "CS0004728"}
    mock_crm_api.add(
        responses.POST,
        f"{BASE_URL}ticketing/ServiceRequests",
        json=expected_response,
        status=HTTPStatus.CREATED,
    )
    service_request = ServiceRequest(
        summary="Test summary",
        title="Test title",
    )

    result = crm_client.create_service_request("ORD-001", service_request)

    assert result == expected_response


def test_create_service_request_http_error(crm_client, mock_crm_api, mock_oauth_token):
    mock_crm_api.add(
        responses.POST,
        f"{BASE_URL}ticketing/ServiceRequests",
        json={"error": "Bad Request"},
        status=HTTPStatus.BAD_REQUEST,
    )
    service_request = ServiceRequest()

    with pytest.raises(CRMHttpError) as exc_info:
        crm_client.create_service_request("ORD-001", service_request)

    assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST


def test_get_service_request_success(crm_client, mock_crm_api, mock_oauth_token):
    expected_response = {"id": "CS0004728", "status": "Open"}
    mock_crm_api.add(
        responses.GET,
        f"{BASE_URL}ticketing/ServiceRequests/CS0004728",
        json=expected_response,
        status=HTTPStatus.OK,
    )

    result = crm_client.get_service_request("ORD-001", "CS0004728")

    assert result == expected_response


def test_get_service_request_not_found(crm_client, mock_crm_api, mock_oauth_token):
    mock_crm_api.add(
        responses.GET,
        f"{BASE_URL}ticketing/ServiceRequests/CS0004728",
        json={"error": "Not Found"},
        status=HTTPStatus.NOT_FOUND,
    )

    with pytest.raises(CRMNotFoundError):
        crm_client.get_service_request("ORD-001", "CS0004728")


def test_get_service_request_http_error(crm_client, mock_crm_api, mock_oauth_token):
    mock_crm_api.add(
        responses.GET,
        f"{BASE_URL}ticketing/ServiceRequests/CS0004728",
        json={"error": "Server Error"},
        status=HTTPStatus.INTERNAL_SERVER_ERROR,
    )

    with pytest.raises(CRMHttpError) as exc_info:
        crm_client.get_service_request("ORD-001", "CS0004728")

    assert exc_info.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


def test_token_refreshed_on_first_request(crm_client, mock_crm_api, mock_oauth_token):
    mock_crm_api.add(
        responses.GET,
        f"{BASE_URL}ticketing/ServiceRequests/CS001",
        json={"id": "CS001"},
        status=HTTPStatus.OK,
    )

    crm_client.get_service_request("ORD-001", "CS001")  # act

    assert "Authorization" in crm_client.headers


def test_authorization_header_is_set(crm_client, mock_crm_api, mock_oauth_token):
    mock_crm_api.add(
        responses.GET,
        f"{BASE_URL}ticketing/ServiceRequests/CS001",
        json={"id": "CS001"},
        status=HTTPStatus.OK,
    )

    crm_client.get_service_request("ORD-001", "CS001")  # act

    assert crm_client.headers["Authorization"] == "Bearer test-token"


def test_api_version_header_is_set(crm_client, mock_crm_api, mock_oauth_token):
    mock_crm_api.add(
        responses.GET,
        f"{BASE_URL}ticketing/ServiceRequests/CS001",
        json={"id": "CS001"},
        status=HTTPStatus.OK,
    )

    crm_client.get_service_request("ORD-001", "CS001")  # act

    assert crm_client.headers["x-api-version"] == "3.0.0"


def test_token_not_refreshed_when_valid(crm_client, mock_crm_api, mock_oauth_token):
    mock_crm_api.add(
        responses.GET,
        f"{BASE_URL}ticketing/ServiceRequests/CS001",
        json={"id": "CS001"},
        status=HTTPStatus.OK,
    )
    mock_crm_api.add(
        responses.GET,
        f"{BASE_URL}ticketing/ServiceRequests/CS002",
        json={"id": "CS002"},
        status=HTTPStatus.OK,
    )
    crm_client.get_service_request("ORD-001", "CS001")

    crm_client.get_service_request("ORD-001", "CS002")  # act

    mock_oauth_token.assert_called_once()


def test_get_service_client_singleton(mocker):
    mocker.patch(
        "swo_aws_extension.swo.crm_service.client._CRMClientFactory._instance",
        None,
    )

    result = get_service_client()  # act

    second_client = get_service_client()
    assert result is second_client


def test_service_request_to_api_dict():
    service_request = ServiceRequest(
        summary="Test summary",
        title="Test title",
        additional_info="Additional info",
    )

    result = service_request.to_api_dict()

    assert result["summary"] == "Test summary"
    assert result["title"] == "Test title"
    assert result["additionalInfo"] == "Additional info"


def test_service_request_default_values():
    service_request = ServiceRequest()

    result = service_request.to_api_dict()

    assert "externalUserEmail" in result
    assert "externalUsername" in result
    assert "requester" in result
    assert "subService" in result
    assert "serviceType" in result


def test_request_with_empty_url(crm_client, mock_crm_api, mock_oauth_token):
    mock_crm_api.add(
        responses.GET,
        BASE_URL,
        json={"status": "ok"},
        status=HTTPStatus.OK,
    )

    result = crm_client.get(url="")  # act

    assert result.status_code == HTTPStatus.OK
