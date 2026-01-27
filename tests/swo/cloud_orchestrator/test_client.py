"""Tests for Cloud Orchestrator client."""

from http import HTTPStatus

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
