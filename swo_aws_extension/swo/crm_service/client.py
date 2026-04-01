import logging
from dataclasses import dataclass
from functools import wraps
from http import HTTPStatus

import requests

from swo_aws_extension.config import Config, get_config
from swo_aws_extension.constants import (
    CRM_EXTERNAL_EMAIL,
    CRM_EXTERNAL_USERNAME,
    CRM_GLOBAL_EXT_USER_ID,
    CRM_REQUESTER,
    CRM_SERVICE_TYPE,
    CRM_SUB_SERVICE,
)
from swo_aws_extension.swo.base_client import OAuthSessionClient
from swo_aws_extension.swo.crm_service.errors import (
    CRMHttpError,
    CRMNotFoundError,
)

logger = logging.getLogger(__name__)


def wrap_http_error(func):
    """Decorator to wrap HTTP errors into CRM errors."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except requests.HTTPError as err:
            if err.response.status_code == HTTPStatus.NOT_FOUND:
                raise CRMNotFoundError(err.response.text) from err
            raise CRMHttpError(err.response.status_code, err.response.text) from err

    return wrapper


@dataclass
class ServiceRequest:
    """Service request API entity."""

    external_user_email: str = CRM_EXTERNAL_EMAIL
    external_username: str = CRM_EXTERNAL_USERNAME
    requester: str = CRM_REQUESTER
    sub_service: str = CRM_SUB_SERVICE
    global_academic_ext_user_id: str = CRM_GLOBAL_EXT_USER_ID
    additional_info: str = ""
    summary: str = ""
    title: str = ""
    service_type: str = CRM_SERVICE_TYPE

    def to_api_dict(self) -> dict:
        """Converts to dict for CRM API."""
        return {
            "externalUserEmail": self.external_user_email,
            "externalUsername": self.external_username,
            "requester": self.requester,
            "subService": self.sub_service,
            "globalacademicExtUserId": self.global_academic_ext_user_id,
            "additionalInfo": self.additional_info,
            "summary": self.summary,
            "title": self.title,
            "serviceType": self.service_type,
        }


class CRMServiceClient(OAuthSessionClient):
    """Client to interact with CRM system."""

    def __init__(self, config: Config, api_version: str = "3.0.0"):
        super().__init__(
            oauth_url=config.crm_oauth_url,
            client_id=config.crm_client_id,
            client_secret=config.crm_client_secret,
            audience=config.crm_audience,
            base_url=config.crm_api_base_url,
        )
        self._api_version = api_version

    @wrap_http_error
    def create_service_request(self, order_id: str, service_request: ServiceRequest) -> dict:
        """Create a service request.

        Args:
            order_id: MPT order id.
            service_request: Service request.

        Returns:
            Dictionary with created service request id {"id": "CS0004728"}.
        """
        response = self.post(
            url="/ticketing/ServiceRequests",
            json=service_request.to_api_dict(),
            headers={"x-correlation-id": order_id},
        )
        response.raise_for_status()
        return response.json()

    @wrap_http_error
    def get_service_request(self, order_id: str, service_request_id: str) -> dict:
        """Retrieve a service request from CRM system.

        Args:
            order_id: MPT order id.
            service_request_id: Service request id.

        Returns:
            Dictionary with service request details.
        """
        response = self.get(
            url=f"/ticketing/ServiceRequests/{service_request_id}",
            headers={"x-correlation-id": order_id},
        )
        response.raise_for_status()
        return response.json()

    def _build_auth_headers(self, token: dict) -> dict:
        """Build auth headers including the CRM API version."""
        headers = super()._build_auth_headers(token)
        headers["x-api-version"] = self._api_version
        return headers


class _CRMClientFactory:
    """Factory for CRM client singleton."""

    _instance: CRMServiceClient | None = None

    @classmethod
    def get_client(cls) -> CRMServiceClient:
        """Get CRM client singleton instance."""
        if cls._instance is not None:
            return cls._instance
        config = get_config()
        cls._instance = CRMServiceClient(
            config=config,
        )
        return cls._instance


def get_service_client() -> CRMServiceClient:
    """Get CRM client singleton instance."""
    return _CRMClientFactory.get_client()
