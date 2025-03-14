from dataclasses import dataclass
from urllib.parse import urljoin

from requests import Session
from requests.adapters import HTTPAdapter, Retry


class ServiceCRMException(Exception):
    pass


@dataclass
class ServiceRequest:
    """
    Example:
    {
      "externalUserEmail": "marketplace@softwareone.com",
      "externalUsername": "mpt@marketplace.com",
      "requester": "Supplier.Portal",
      "subService": "Service Activation",
      "globalacademicExtUserId": "notapplicable",
      "additionalInfo": "Service Activation",
      "summary": "Request for Service Activation",
      "title": "Request for Service Activation for SW-CCO-123-123",
      "serviceType": "MarketPlaceServiceActivation"

    }
    """
    externalUserEmail: str
    externalUsername: str
    requester: str
    subService: str
    globalacademicExtUserId: str
    additionalInfo: str
    summary: str
    title: str
    serviceType: str


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
        self.mount("http://", HTTPAdapter(
            max_retries=retries,
            pool_maxsize=36,
        ))
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
        data = service_request.__dict__
        self.order_id=order_id
        response = self.post(
            url="/ticketing/ServiceRequests",
            json=data,
            headers=self._prepare_headers(order_id),
        )
        response.raise_for_status()
        return response.json()

    def get_service_requests(self, order_id, service_request_id: str) -> ServiceRequest:
        response = self.get(
            url=f"/ticketing/ServiceRequests/{service_request_id}",
            headers=self._prepare_headers(order_id),
        )
        response.raise_for_status()
        return response.json()

