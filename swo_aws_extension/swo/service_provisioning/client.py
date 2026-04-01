from functools import wraps

import requests

from swo_aws_extension.config import Config, get_config
from swo_aws_extension.swo.base_client import OAuthSessionClient
from swo_aws_extension.swo.service_provisioning.errors import ServiceProvisioningHttpError
from swo_aws_extension.swo.service_provisioning.models import (
    ServiceOnboardingRequest,
    ServiceOnboardingResponse,
)

API_VERSION = "1.0"


def wrap_http_error(func):
    """Decorator to wrap HTTP errors into ServiceProvisioning errors."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except requests.HTTPError as err:
            raise ServiceProvisioningHttpError(err.response.status_code, err.response.text) from err

    return wrapper


class ServiceProvisioningClient(OAuthSessionClient):
    """Client to interact with the Services Provisioning API."""

    def __init__(self, config: Config) -> None:
        super().__init__(
            oauth_url=config.svc_provisioning_oauth_url,
            client_id=config.svc_provisioning_client_id,
            client_secret=config.svc_provisioning_client_secret,
            audience=config.svc_provisioning_audience,
            base_url=config.svc_provisioning_api_base_url,
        )

    @wrap_http_error
    def onboard(self, request: ServiceOnboardingRequest) -> ServiceOnboardingResponse:
        """Onboard a CCO contract into Service Provisioning.

        Args:
            request: Onboarding request with contract info and contacts.

        Returns:
            ServiceOnboardingResponse with the erpProjectNo.
        """
        response = self.post(
            url="service-provisioning/api/serviceonboarding",
            json=request.to_api_dict(),
            headers={"x-api-version": API_VERSION},
        )
        response.raise_for_status()
        return ServiceOnboardingResponse(erp_project_no=response.json()["erpProjectNo"])


class _ServiceProvisioningClientFactory:
    """Factory for Service Provisioning client singleton."""

    _instance: ServiceProvisioningClient | None = None

    @classmethod
    def get_client(cls) -> ServiceProvisioningClient:
        """Get Service Provisioning client singleton instance."""
        if cls._instance is not None:
            return cls._instance
        cls._instance = ServiceProvisioningClient(config=get_config())
        return cls._instance


def get_service_provisioning_client() -> ServiceProvisioningClient:
    """Get Service Provisioning client singleton instance."""
    return _ServiceProvisioningClientFactory.get_client()
