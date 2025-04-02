from dataclasses import dataclass
from urllib.parse import urljoin

from requests import Session
from requests.adapters import HTTPAdapter, Retry


class ServiceCRMException(Exception):
    pass


@dataclass
class ServiceRequest:
    external_user_email: str
    external_username: str
    requester: str
    sub_service: str
    global_academic_ext_user_id: str
    additional_info: str
    summary: str
    title: str
    service_type: str

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
    def __init__(self, base_url, api_token, api_version="3.0.0"):
        super().__init__()
        self.api_token = api_token
        self.api_version = api_version
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
        self.base_url = f"{base_url}/" if base_url[-1] != "/" else base_url
        self.api_token = api_token

    def request(self, method, url, *args, **kwargs):
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
        return response.json()

    def get_service_requests(self, order_id, service_request_id: str):
        response = self.get(
            url=f"/ticketing/ServiceRequests/{service_request_id}",
            headers=self._prepare_headers(order_id),
        )
        response.raise_for_status()
        return response.json()
