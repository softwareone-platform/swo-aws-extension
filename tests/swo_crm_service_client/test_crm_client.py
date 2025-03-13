import pytest
from requests import PreparedRequest
from requests.models import Response

from swo_crm_service_client.client import CRMServiceClient, ServiceRequest


@pytest.fixture()
def service_request():
    return ServiceRequest(
        external_user_email="user@example.com",
        external_username="username",
        requester="requester",
        sub_service="subService",
        global_academic_ext_user_id="globalacademicExtUserId",
        additional_info="additionalInfo",
        summary="summary",
        title="title",
        service_type="serviceType",
    )


@pytest.fixture()
def crm_client():
    return CRMServiceClient(base_url="http://example.com", api_token="test_token")


def test_to_api_dict(service_request):
    assert service_request.to_api_dict() == {
        "additionalInfo": "additionalInfo",
        "externalUserEmail": "user@example.com",
        "externalUsername": "username",
        "globalacademicExtUserId": "globalacademicExtUserId",
        "requester": "requester",
        "serviceType": "serviceType",
        "subService": "subService",
        "summary": "summary",
        "title": "title",
    }


def test_preapre_headers(crm_client):
    order_id = "ORD-0000-0000"
    headers = crm_client._prepare_headers(order_id)
    assert headers["x-correlation-id"] == order_id


def test_service_request_model():
    service_request = ServiceRequest(
        external_user_email="user@example.com",
        external_username="username",
        requester="requester",
        sub_service="subService",
        global_academic_ext_user_id="globalacademicExtUserId",
        additional_info="additionalInfo",
        summary="summary",
        title="title",
        service_type="serviceType",
    )
    expected_data = {
        "externalUserEmail": "user@example.com",
        "externalUsername": "username",
        "requester": "requester",
        "subService": "subService",
        "globalacademicExtUserId": "globalacademicExtUserId",
        "additionalInfo": "additionalInfo",
        "summary": "summary",
        "title": "title",
        "serviceType": "serviceType",
    }
    assert service_request.to_api_dict() == expected_data


def test_create_service_request(crm_client, service_request, mocker):
    mock_response = mocker.Mock(spec=Response)
    mock_response.json.return_value = {"id": "12345"}
    mock_response.status_code = 200
    mocker.patch.object(crm_client, "post", return_value=mock_response)

    order_id = "ORD-0000-0000"
    response = crm_client.create_service_request(order_id, service_request)

    assert response == {"id": "12345"}

    expected_json = {
        "additionalInfo": "additionalInfo",
        "externalUserEmail": "user@example.com",
        "externalUsername": "username",
        "globalacademicExtUserId": "globalacademicExtUserId",
        "requester": "requester",
        "serviceType": "serviceType",
        "subService": "subService",
        "summary": "summary",
        "title": "title",
    }
    crm_client.post.assert_called_once_with(
        url="/ticketing/ServiceRequests",
        json=expected_json,
        headers={"x-correlation-id": order_id},
    )


def test_get_service_request(crm_client, mocker):
    mock_response = mocker.Mock(spec=Response)
    service_request_response = {"id": "12345", "status": "new"}
    mock_response.json.return_value = service_request_response
    mock_response.status_code = 200
    mocker.patch.object(crm_client, "get", return_value=mock_response)

    order_id = "ORD-0000-0000"
    response = crm_client.get_service_requests(order_id, "12345")

    assert response == service_request_response
    crm_client.get.assert_called_once_with(
        url="/ticketing/ServiceRequests/12345", headers={"x-correlation-id": order_id}
    )


def test_client_headers(crm_client, service_request, mocker):
    mock_response = mocker.Mock(spec=Response)
    mock_response.json.return_value = {"id": "12345"}
    mock_response.status_code = 200
    mocker.patch.object(crm_client, "send", return_value=mock_response)

    order_id = "ORD-0000-0000"
    response = crm_client.create_service_request(order_id, service_request)
    assert response == {"id": "12345"}

    create_service_request: PreparedRequest = crm_client.send.call_args[0][0]
    csr_expected_headers = {
        "User-Agent": "swo-extensions/1.0",
        "Accept-Encoding": "gzip, deflate, zstd",
        "Accept": "*/*",
        "Connection": "keep-alive",
        "Authorization": "Bearer test_token",
        "x-api-version": "3.0.0",
        "x-correlation-id": "ORD-0000-0000",
        "Content-Length": "287",
        "Content-Type": "application/json",
    }
    assert create_service_request.headers == csr_expected_headers
    assert create_service_request.url == "http://example.com/ticketing/ServiceRequests"
