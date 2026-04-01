from http import HTTPStatus

import pytest
import responses

from swo_aws_extension.swo.service_provisioning.client import (
    ServiceProvisioningClient,
    get_service_provisioning_client,
)
from swo_aws_extension.swo.service_provisioning.errors import ServiceProvisioningHttpError
from swo_aws_extension.swo.service_provisioning.models import (
    ServiceContact,
    ServiceOnboardingRequest,
)

SVC_BASE_URL = "https://swo-ip-apim-uat.azure-api.net/"
MODULE = "swo_aws_extension.swo.service_provisioning.client"
ONBOARD_URL = f"{SVC_BASE_URL}service-provisioning/api/serviceonboarding"


@pytest.fixture
def mock_oauth_token(requests_mocker, config):
    requests_mocker.add(
        responses.POST,
        config.svc_provisioning_oauth_url,
        json={"access_token": "test-token", "expires_in": 3600},
        status=HTTPStatus.OK,
    )
    return requests_mocker


@pytest.fixture
def svc_client(config):
    return ServiceProvisioningClient(config)


@pytest.fixture
def mock_svc_api(mock_oauth_token, requests_mocker):
    """HTTP mock for Service Provisioning API.

    Depends on mock_oauth_token so get_auth_token is patched before
    responses.RequestsMock intercepts HTTP.
    """
    return requests_mocker


@pytest.fixture
def sample_request():
    return ServiceOnboardingRequest(
        erp_client_id="SWO_CH",
        contract_no="CH-CCO-331705",
        service_description="DWE",
        contacts=[
            ServiceContact(
                first_name="user",
                last_name="last_name",
                email="test@mail.com",
                phone_number="+34666666666",
                language_code="ES",
            )
        ],
    )


def test_onboard_success(svc_client, mock_svc_api, sample_request):
    mock_svc_api.add(
        responses.POST,
        ONBOARD_URL,
        json={"erpProjectNo": "PRO-123-13-132"},
        status=HTTPStatus.OK,
    )

    result = svc_client.onboard(sample_request)  # act

    assert result.erp_project_no == "PRO-123-13-132"


def test_onboard_http_error(svc_client, mock_svc_api, sample_request):
    mock_svc_api.add(
        responses.POST,
        ONBOARD_URL,
        json={"error": "Bad Request"},
        status=HTTPStatus.BAD_REQUEST,
    )

    with pytest.raises(ServiceProvisioningHttpError) as exc_info:
        svc_client.onboard(sample_request)  # act

    assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST


def test_onboard_sends_api_version_header(svc_client, mock_svc_api, sample_request):
    mock_svc_api.add(
        responses.POST,
        ONBOARD_URL,
        json={"erpProjectNo": "PRO-123-13-132"},
        status=HTTPStatus.OK,
    )

    svc_client.onboard(sample_request)  # act

    request_headers = mock_svc_api.calls[-1].request.headers
    assert request_headers["x-api-version"] == "1.0"


def test_get_service_provisioning_client_singleton(mocker):
    mocker.patch(
        f"{MODULE}._ServiceProvisioningClientFactory._instance",
        None,
    )

    result = get_service_provisioning_client()  # act

    second = get_service_provisioning_client()
    assert result is second


def test_service_onboarding_request_to_api_dict(sample_request):
    payload = sample_request.to_api_dict()  # act

    assert payload["erpClientId"] == "SWO_CH"
    assert payload["contractNo"] == "CH-CCO-331705"
    assert payload["serviceDescription"] == "DWE"


def test_service_onboarding_request_to_api_dict_contacts(sample_request):
    payload = sample_request.to_api_dict()  # act

    assert len(payload["contacts"]) == 1
    assert payload["contacts"][0]["email"] == "test@mail.com"
    assert payload["contacts"][0]["languageCode"] == "ES"
