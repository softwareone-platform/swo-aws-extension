import logging
import time
from dataclasses import dataclass
from json import JSONDecodeError
from urllib.parse import urljoin

from requests import Session
from requests.adapters import HTTPAdapter, Retry

from swo_aws_extension.constants import (
    CRM_EXTERNAL_EMAIL,
    CRM_EXTERNAL_USERNAME,
    CRM_GLOBAL_EXT_USER_ID,
    CRM_REQUESTER,
    CRM_SERVICE_TYPE,
    CRM_SUB_SERVICE,
)
from swo_aws_extension.crm_service_client.config import CRMConfig
from swo_aws_extension.openid import get_openid_token

logger = logging.getLogger(__name__)


class ServiceCRMException(Exception):
    pass


@dataclass
class ServiceRequest:
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


class CRMServiceClient(Session):
    def __init__(self, config, api_version="3.0.0"):
        super().__init__()
        self.config = config
        self.api_version = api_version
        token = self.get_crm_token()
        self.api_token = token["access_token"]
        self.token_expiry = time.time() + token["expires_in"]
        retries = Retry(
            total=5,
            backoff_factor=0.1,
            status_forcelist=[500, 502, 503, 504],
        )
        self.mount(
            "http://",
            HTTPAdapter(
                max_retries=retries,
                pool_maxsize=36,
            ),
        )
        self.headers.update(
            {
                "User-Agent": "swo-extensions/1.0",
                "Authorization": f"Bearer {self.api_token}",
                "x-api-version": self.api_version,
            },
        )
        self.base_url = (
            f"{self.config.base_url}/" if self.config.base_url[-1] != "/" else self.config.base_url
        )

    def is_token_expired(self):
        """Check if the token is expired."""
        if self.token_expiry is None:
            return True
        return time.time() >= (self.token_expiry - 60)

    def refresh_token(self):
        """Refresh the CRM token if it is expired."""
        token = self.get_crm_token()
        self.api_token = token["access_token"]
        self.token_expiry = time.time() + token["expires_in"]

        self.headers["Authorization"] = f"Bearer {self.api_token}"

    def get_crm_token(self):
        """Get a new CRM token"""
        return get_openid_token(
            endpoint=self.config.oauth_url,
            client_id=self.config.client_id,
            client_secret=self.config.client_secret,
            scope=None,
            audience=self.config.audience,
        )

    def request(self, method, url, *args, **kwargs):
        if self.is_token_expired():
            self.refresh_token()
        url = self._join_url(url)
        return super().request(method, url, *args, **kwargs)

    def prepare_request(self, request, *args, **kwargs):
        request.url = self._join_url(request.url)
        return super().prepare_request(request, *args, **kwargs)

    def _join_url(self, url):
        url = url[1:] if url[0] == "/" else url
        return urljoin(self.base_url, url)

    def _prepare_headers(self, order_id):
        return {"x-correlation-id": order_id}

    def create_service_request(self, order_id, service_request: ServiceRequest):
        """
        Create a service request
        :param order_id:
        :param service_request:
        :return: {"id": "CS0004728"}
        """
        data = service_request.to_api_dict()
        response = self.post(
            url="/ticketing/ServiceRequests",
            json=data,
            headers=self._prepare_headers(order_id),
        )
        response.raise_for_status()
        try:
            return response.json()
        except JSONDecodeError:
            logger.error(
                f"JSONDecodeError - Malformed response from ServiceNow CRM during service"
                f" request. Status code: {response.status_code} - {response.content}"
            )
            raise

    def get_service_requests(self, order_id, service_request_id: str):
        response = self.get(
            url=f"/ticketing/ServiceRequests/{service_request_id}",
            headers=self._prepare_headers(order_id),
        )
        response.raise_for_status()
        return response.json()


_CRM_CLIENT = None


def get_service_client() -> CRMServiceClient:
    config = CRMConfig()
    global _CRM_CLIENT
    if not _CRM_CLIENT:
        _CRM_CLIENT = CRMServiceClient(
            config=config,
        )
    return _CRM_CLIENT
