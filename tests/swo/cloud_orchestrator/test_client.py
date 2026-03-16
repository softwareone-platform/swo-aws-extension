"""Tests for Cloud Orchestrator client."""

from http import HTTPStatus
from urllib.parse import quote

import pytest
import responses

from swo_aws_extension.swo.cloud_orchestrator.client import CloudOrchestratorClient
from swo_aws_extension.swo.cloud_orchestrator.errors import (
    CloudOrchestratorHttpError,
    CloudOrchestratorNotFoundError,
)

BASE_URL = "https://cloud-orchestrator.test.com/"


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
