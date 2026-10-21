"""Tests for Cloud Orchestrator client."""

import logging
from http import HTTPStatus
from urllib.parse import quote

import pytest
import requests
import responses

from swo_aws_extension.swo.cloud_orchestrator.client import CloudOrchestratorClient
from swo_aws_extension.swo.cloud_orchestrator.errors import (
    CloudOrchestratorAuthError,
    CloudOrchestratorConnectionError,
    CloudOrchestratorEmptyResponseError,
    CloudOrchestratorHttpError,
    CloudOrchestratorInvalidJsonError,
    CloudOrchestratorNotFoundError,
    CloudOrchestratorUnexpectedResponseError,
)
from swo_aws_extension.swo.openid.errors import OpenIDTokenError

BASE_URL = "https://cloud-orchestrator.test.com/"
ACCOUNT_ID = "677276121359"
EXECUTION_ARN = "arn:aws:states:us-east-1:123456789012:execution:test"
BOOTSTRAP_ROLE_PATH = f"api/v1/bootstrap-role/check?target_account_id={ACCOUNT_ID}"
DEPLOYMENT_STATUS_PATH = f"api/v1/deployments/execution-arn/{quote(EXECUTION_ARN, safe='')}"
ENDPOINTS = (
    pytest.param(
        "get_bootstrap_role_status",
        ACCOUNT_ID,
        responses.GET,
        BOOTSTRAP_ROLE_PATH,
        id="bootstrap-role",
    ),
    pytest.param(
        "onboard_customer",
        {"scu": "DM-SCU-000000"},
        responses.POST,
        "api/v1/marketplace/onboard",
        id="onboard",
    ),
    pytest.param(
        "upgrade_customer",
        {"scu": "DM-SCU-000000", "master_payer_id": "104688972956"},
        responses.POST,
        "api/v1/marketplace/upgrade",
        id="upgrade",
    ),
    pytest.param(
        "get_deployment_status",
        EXECUTION_ARN,
        responses.GET,
        DEPLOYMENT_STATUS_PATH,
        id="deployment-status",
    ),
)


@pytest.fixture
def mock_openid_client(mocker):
    return mocker.patch("swo_aws_extension.swo.cloud_orchestrator.client.OpenIDClient")


@pytest.fixture
def cloud_orchestrator_client(settings, mock_openid_client, config):
    settings.EXTENSION_CONFIG["CLOUD_ORCHESTRATOR_API_BASE_URL"] = BASE_URL
    mock_openid_client.return_value.fetch_access_token.return_value = "test-token"
    return CloudOrchestratorClient(config)


@pytest.fixture
def mock_api(requests_mocker):
    return requests_mocker


def test_init_sets_base_url_with_trailing_slash(settings, mock_openid_client, config):
    settings.EXTENSION_CONFIG["CLOUD_ORCHESTRATOR_API_BASE_URL"] = "https://api.test.com"
    mock_openid_client.return_value.fetch_access_token.return_value = "test-token"

    result = CloudOrchestratorClient(config)

    assert result.base_url == "https://api.test.com/"


def test_init_preserves_trailing_slash(settings, mock_openid_client, config):
    settings.EXTENSION_CONFIG["CLOUD_ORCHESTRATOR_API_BASE_URL"] = "https://api.test.com/"
    mock_openid_client.return_value.fetch_access_token.return_value = "test-token"

    result = CloudOrchestratorClient(config)

    assert result.base_url == "https://api.test.com/"


def test_get_bootstrap_role_status_success(cloud_orchestrator_client, mock_api, mock_openid_client):
    expected_response = {"deployed": True, "message": "Bootstrap role is deployed"}
    mock_api.add(
        responses.GET,
        f"{BASE_URL}api/v1/bootstrap-role/check?target_account_id=677276121359",
        json=expected_response,
        status=HTTPStatus.OK,
    )

    result = cloud_orchestrator_client.get_bootstrap_role_status("677276121359")

    assert result == expected_response
    assert result["deployed"] is True
    assert result["message"] == "Bootstrap role is deployed"


def test_get_bootstrap_role_status_not_deployed(
    cloud_orchestrator_client, mock_api, mock_openid_client
):
    expected_response = {"deployed": False, "message": "Bootstrap role not found"}
    mock_api.add(
        responses.GET,
        f"{BASE_URL}api/v1/bootstrap-role/check?target_account_id=677276121359",
        json=expected_response,
        status=HTTPStatus.OK,
    )

    result = cloud_orchestrator_client.get_bootstrap_role_status("677276121359")

    assert result == expected_response
    assert result["deployed"] is False


def test_get_bootstrap_role_status_not_found(
    cloud_orchestrator_client, mock_api, mock_openid_client
):
    mock_api.add(
        responses.GET,
        f"{BASE_URL}api/v1/bootstrap-role/check?target_account_id=677276121359",
        json={"error": "Not found"},
        status=HTTPStatus.NOT_FOUND,
    )

    with pytest.raises(CloudOrchestratorNotFoundError):
        cloud_orchestrator_client.get_bootstrap_role_status("677276121359")


def test_get_bootstrap_role_status_http_error(
    cloud_orchestrator_client, mock_api, mock_openid_client
):
    mock_api.add(
        responses.GET,
        f"{BASE_URL}api/v1/bootstrap-role/check?target_account_id=677276121359",
        json={"error": "Internal Server Error"},
        status=HTTPStatus.INTERNAL_SERVER_ERROR,
    )

    with pytest.raises(CloudOrchestratorHttpError) as exc_info:
        cloud_orchestrator_client.get_bootstrap_role_status("677276121359")

    assert exc_info.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


def test_authorization_header_is_set(cloud_orchestrator_client, mock_api, mock_openid_client):
    mock_api.add(
        responses.GET,
        f"{BASE_URL}api/v1/bootstrap-role/check?target_account_id=123",
        json={"deployed": True, "message": "OK"},
        status=HTTPStatus.OK,
    )

    cloud_orchestrator_client.get_bootstrap_role_status("123")  # act

    assert cloud_orchestrator_client.headers["Authorization"] == "Bearer test-token"


def test_onboard_customer_success(cloud_orchestrator_client, mock_api, mock_openid_client):
    expected_response = {"execution_arn": "arn:aws:states:us-east-1:123456789012:execution:test"}
    payload = {
        "customer": "Acme Corp",
        "scu": "US-SCU-999999",
        "pma": "123456789012",
        "master_payer_id": "987654321098",
        "support_type": "PartnerLedSupport",
        "onboarding_type": "FullCMS",
    }
    mock_api.add(
        responses.POST,
        f"{BASE_URL}api/v1/marketplace/onboard",
        json=expected_response,
        status=HTTPStatus.OK,
    )

    result = cloud_orchestrator_client.onboard_customer(payload)

    assert result == expected_response


def test_onboard_customer_http_error(cloud_orchestrator_client, mock_api, mock_openid_client):
    mock_api.add(
        responses.POST,
        f"{BASE_URL}api/v1/marketplace/onboard",
        json={"error": "Internal Server Error"},
        status=HTTPStatus.INTERNAL_SERVER_ERROR,
    )

    with pytest.raises(CloudOrchestratorHttpError) as exc_info:
        cloud_orchestrator_client.onboard_customer({})

    assert exc_info.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


def test_onboard_customer_not_found(cloud_orchestrator_client, mock_api, mock_openid_client):
    mock_api.add(
        responses.POST,
        f"{BASE_URL}api/v1/marketplace/onboard",
        json={"error": "Not found"},
        status=HTTPStatus.NOT_FOUND,
    )

    with pytest.raises(CloudOrchestratorNotFoundError):
        cloud_orchestrator_client.onboard_customer({})


def test_upgrade_customer_success(cloud_orchestrator_client, mock_api, mock_openid_client, caplog):
    caplog.set_level(logging.INFO)
    expected_response = {
        "executions": [
            {
                "execution_arn": "arn:aws:states:us-east-1:123456789012:execution:test",
                "deployment_id": "f54e1c4b-3d90-4489-8ec6-f2b1157daf3b",
            }
        ]
    }
    payload = {"scu": "DM-SCU-000000", "master_payer_id": "104688972956"}
    mock_api.add(
        responses.POST,
        f"{BASE_URL}api/v1/marketplace/upgrade",
        match=[responses.matchers.json_params_matcher(payload)],
        json=expected_response,
        status=HTTPStatus.OK,
    )

    result = cloud_orchestrator_client.upgrade_customer(payload)

    assert result == expected_response
    assert (
        f"Cloud Orchestrator upgrade request: POST {BASE_URL}api/v1/marketplace/upgrade "
        "payload={'scu': 'DM-SCU-000000', 'master_payer_id': '104688972956'}"
    ) in caplog.text
    assert (
        "Cloud Orchestrator upgrade response: status=200 "
        'body={"executions": [{"execution_arn": '
        '"arn:aws:states:us-east-1:123456789012:execution:test", '
        '"deployment_id": "f54e1c4b-3d90-4489-8ec6-f2b1157daf3b"}]}'
    ) in caplog.text


def test_upgrade_customer_http_error(
    cloud_orchestrator_client, mock_api, mock_openid_client, caplog
):
    caplog.set_level(logging.INFO)
    mock_api.add(
        responses.POST,
        f"{BASE_URL}api/v1/marketplace/upgrade",
        json={"error": "Internal Server Error"},
        status=HTTPStatus.INTERNAL_SERVER_ERROR,
    )

    with pytest.raises(CloudOrchestratorHttpError) as exc_info:
        cloud_orchestrator_client.upgrade_customer({"scu": "US-SCU-999999"})

    assert exc_info.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert (
        f"upgrade request: POST {BASE_URL}api/v1/marketplace/upgrade "
        "payload={'scu': 'US-SCU-999999'}"
    ) in caplog.text
    assert 'upgrade response: status=500 body={"error": "Internal Server Error"}' in caplog.text


def test_upgrade_customer_not_found(cloud_orchestrator_client, mock_api, mock_openid_client):
    mock_api.add(
        responses.POST,
        f"{BASE_URL}api/v1/marketplace/upgrade",
        json={"error": "Not found"},
        status=HTTPStatus.NOT_FOUND,
    )

    with pytest.raises(CloudOrchestratorNotFoundError):
        cloud_orchestrator_client.upgrade_customer({})


def test_get_deployment_status_success(cloud_orchestrator_client, mock_api, mock_openid_client):
    execution_arn = "arn:aws:states:us-east-1:123456789012:execution:test"
    expected_response = {"status": "succeeded"}
    mock_api.add(
        responses.GET,
        f"{BASE_URL}api/v1/deployments/execution-arn/{quote(execution_arn, safe='')}",
        json=expected_response,
        status=HTTPStatus.OK,
    )

    result = cloud_orchestrator_client.get_deployment_status(execution_arn)

    assert result == expected_response
    assert result["status"] == "succeeded"


def test_get_deployment_status_http_error(cloud_orchestrator_client, mock_api, mock_openid_client):
    execution_arn = "arn:aws:states:us-east-1:123456789012:execution:test"
    mock_api.add(
        responses.GET,
        f"{BASE_URL}api/v1/deployments/execution-arn/{quote(execution_arn, safe='')}",
        json={"error": "Internal Server Error"},
        status=HTTPStatus.INTERNAL_SERVER_ERROR,
    )

    with pytest.raises(CloudOrchestratorHttpError) as exc_info:
        cloud_orchestrator_client.get_deployment_status(execution_arn)

    assert exc_info.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


def test_get_deployment_status_not_found(cloud_orchestrator_client, mock_api, mock_openid_client):
    execution_arn = "arn:aws:states:us-east-1:123456789012:execution:test"
    mock_api.add(
        responses.GET,
        f"{BASE_URL}api/v1/deployments/execution-arn/{quote(execution_arn, safe='')}",
        json={"error": "Not found"},
        status=HTTPStatus.NOT_FOUND,
    )

    with pytest.raises(CloudOrchestratorNotFoundError):
        cloud_orchestrator_client.get_deployment_status(execution_arn)


def test_request_strips_leading_slash_from_url(
    cloud_orchestrator_client, mock_api, mock_openid_client
):
    mock_api.add(
        responses.GET,
        f"{BASE_URL}api/v1/bootstrap-role/check?target_account_id=123",
        json={"deployed": True, "message": "OK"},
        status=HTTPStatus.OK,
    )

    result = cloud_orchestrator_client.get("/api/v1/bootstrap-role/check?target_account_id=123")

    assert result.status_code == HTTPStatus.OK


@pytest.mark.parametrize(("method_name", "argument", "http_method", "path"), ENDPOINTS)
@pytest.mark.parametrize(
    ("response_kwargs", "error_class", "reason"),
    [
        (
            {"status": HTTPStatus.INTERNAL_SERVER_ERROR, "json": {"error": "boom"}},
            CloudOrchestratorHttpError,
            "error status returned",
        ),
        (
            {"status": HTTPStatus.NOT_FOUND, "json": {"error": "Not found"}},
            CloudOrchestratorNotFoundError,
            "resource not found",
        ),
        (
            {"body": requests.Timeout("read timed out")},
            CloudOrchestratorConnectionError,
            "request not completed: read timed out",
        ),
        (
            {"body": requests.ConnectionError("connection refused")},
            CloudOrchestratorConnectionError,
            "request not completed: connection refused",
        ),
        (
            {"status": HTTPStatus.OK, "body": ""},
            CloudOrchestratorEmptyResponseError,
            "response body is empty",
        ),
        (
            {"status": HTTPStatus.OK, "body": "<html>"},
            CloudOrchestratorInvalidJsonError,
            "response body is not valid JSON",
        ),
        (
            {"status": HTTPStatus.OK, "json": ["not", "an", "object"]},
            CloudOrchestratorUnexpectedResponseError,
            "response is a JSON list, not an object",
        ),
    ],
)
def test_endpoint_failure_raises_meaningful_error(
    cloud_orchestrator_client,
    mock_api,
    method_name,
    argument,
    http_method,
    path,
    response_kwargs,
    error_class,
    reason,
):
    mock_api.add(http_method, f"{BASE_URL}{path}", **response_kwargs)

    with pytest.raises(error_class) as exc_info:
        getattr(cloud_orchestrator_client, method_name)(argument)

    assert exc_info.value.reason == reason
    assert exc_info.value.method == http_method
    assert exc_info.value.endpoint == path


@pytest.mark.parametrize(("method_name", "argument", "http_method", "path"), ENDPOINTS)
@pytest.mark.parametrize("token_error", [OpenIDTokenError("invalid client"), KeyError("scope")])
def test_endpoint_token_failure_raises_auth_error(
    cloud_orchestrator_client,
    mock_openid_client,
    method_name,
    argument,
    http_method,
    path,
    token_error,
):
    mock_openid_client.return_value.fetch_access_token.side_effect = token_error

    with pytest.raises(CloudOrchestratorAuthError) as exc_info:
        getattr(cloud_orchestrator_client, method_name)(argument)

    assert exc_info.value.reason.startswith("access token not available: ")
    assert exc_info.value.__cause__ is token_error


def test_http_error_keeps_request_and_response(cloud_orchestrator_client, mock_api):
    mock_api.add(
        responses.POST,
        f"{BASE_URL}api/v1/marketplace/upgrade",
        json={"error": "boom"},
        status=HTTPStatus.INTERNAL_SERVER_ERROR,
    )

    with pytest.raises(CloudOrchestratorHttpError) as exc_info:
        cloud_orchestrator_client.upgrade_customer({"scu": "DM-SCU-000000"})

    assert exc_info.value.operation == "upgrade"
    assert exc_info.value.payload == {"scu": "DM-SCU-000000"}
    assert exc_info.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert exc_info.value.response_content == '{"error": "boom"}'
    assert exc_info.value.message == (
        "Cloud Orchestrator upgrade failed: error status returned "
        '(POST api/v1/marketplace/upgrade, HTTP 500, response: {"error": "boom"})'
    )


@pytest.mark.parametrize(
    ("response_body", "reason"),
    [
        ({}, "response has no 'execution_arn' string"),
        ({"execution_arn": ""}, "response has no 'execution_arn' string"),
        ({"execution_arn": 123}, "response has no 'execution_arn' string"),
    ],
)
def test_onboard_customer_contract_break(
    cloud_orchestrator_client, mock_api, response_body, reason
):
    mock_api.add(
        responses.POST,
        f"{BASE_URL}api/v1/marketplace/onboard",
        json=response_body,
        status=HTTPStatus.OK,
    )

    with pytest.raises(CloudOrchestratorUnexpectedResponseError) as exc_info:
        cloud_orchestrator_client.onboard_customer({})

    assert exc_info.value.reason == reason


@pytest.mark.parametrize(
    ("response_body", "reason"),
    [
        ({}, "response has no 'executions' list"),
        ({"executions": None}, "response has no 'executions' list"),
        ({"executions": []}, "response has an empty 'executions' list"),
        ({"executions": ["arn"]}, "execution 0 has no 'execution_arn' string"),
        (
            {"executions": [{"execution_arn": EXECUTION_ARN}, {"deployment_id": "d-1"}]},
            "execution 1 has no 'execution_arn' string",
        ),
        ({"executions": [{"execution_arn": ""}]}, "execution 0 has no 'execution_arn' string"),
    ],
)
def test_upgrade_customer_contract_break(
    cloud_orchestrator_client, mock_api, response_body, reason
):
    mock_api.add(
        responses.POST,
        f"{BASE_URL}api/v1/marketplace/upgrade",
        json=response_body,
        status=HTTPStatus.OK,
    )

    with pytest.raises(CloudOrchestratorUnexpectedResponseError) as exc_info:
        cloud_orchestrator_client.upgrade_customer({"scu": "DM-SCU-000000"})

    assert exc_info.value.reason == reason


@pytest.mark.parametrize(
    ("response_body", "reason"),
    [
        ({}, "response has an unknown 'status' None"),
        ({"status": "cancelled"}, "response has an unknown 'status' 'cancelled'"),
        ({"status": 1}, "response has an unknown 'status' 1"),
    ],
)
def test_get_deployment_status_contract_break(
    cloud_orchestrator_client, mock_api, response_body, reason
):
    mock_api.add(responses.GET, f"{BASE_URL}{DEPLOYMENT_STATUS_PATH}", json=response_body)

    with pytest.raises(CloudOrchestratorUnexpectedResponseError) as exc_info:
        cloud_orchestrator_client.get_deployment_status(EXECUTION_ARN)

    assert exc_info.value.reason == reason


@pytest.mark.parametrize("status", ["SUCCEEDED", "Failed", "running", "PENDING"])
def test_get_deployment_status_accepts_any_case(cloud_orchestrator_client, mock_api, status):
    mock_api.add(responses.GET, f"{BASE_URL}{DEPLOYMENT_STATUS_PATH}", json={"status": status})

    result = cloud_orchestrator_client.get_deployment_status(EXECUTION_ARN)

    assert result == {"status": status}


@pytest.mark.parametrize("response_body", [{}, {"deployed": "yes"}, {"deployed": None}])
def test_get_bootstrap_role_status_contract_break(
    cloud_orchestrator_client, mock_api, response_body
):
    mock_api.add(responses.GET, f"{BASE_URL}{BOOTSTRAP_ROLE_PATH}", json=response_body)

    with pytest.raises(CloudOrchestratorUnexpectedResponseError) as exc_info:
        cloud_orchestrator_client.get_bootstrap_role_status(ACCOUNT_ID)

    assert exc_info.value.reason == "response has no 'deployed' boolean"


def test_get_bootstrap_role_status_encodes_account_id(cloud_orchestrator_client, mock_api):
    mock_api.add(
        responses.GET,
        f"{BASE_URL}api/v1/bootstrap-role/check?target_account_id=12%2034%2F5",
        json={"deployed": True},
        match=[responses.matchers.query_param_matcher({"target_account_id": "12 34/5"})],
    )

    result = cloud_orchestrator_client.get_bootstrap_role_status("12 34/5")

    assert result == {"deployed": True}


def test_get_endpoint_logs_request_and_response(cloud_orchestrator_client, mock_api, caplog):
    caplog.set_level(logging.INFO)
    mock_api.add(responses.GET, f"{BASE_URL}{DEPLOYMENT_STATUS_PATH}", json={"status": "running"})

    cloud_orchestrator_client.get_deployment_status(EXECUTION_ARN)  # act

    assert (
        "Cloud Orchestrator deployment status check request: "
        f"GET {BASE_URL}{DEPLOYMENT_STATUS_PATH} payload=None"
    ) in caplog.text
    assert (
        'Cloud Orchestrator deployment status check response: status=200 body={"status": "running"}'
    ) in caplog.text
