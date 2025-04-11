from urllib.parse import urljoin

from requests import Session
from requests.adapters import HTTPAdapter, Retry

from swo_aws_extension.openid import get_openid_token


class CCPClient(Session):
    """
    A class to interact with the CCP API.
    """

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.access_token = self.get_ccp_access_token()
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
            {"User-Agent": "swo-extensions/1.0", "Authorization": f"Bearer {self.access_token}"},
        )
        base_url = self.config.ccp_api_base_url
        self.base_url = f"{base_url}/" if base_url[-1] != "/" else base_url

    def get_ccp_access_token(self):
        response = get_openid_token(
            endpoint=self.config.ccp_oauth_url,
            client_id=self.config.ccp_client_id,
            client_secret=self.config.ccp_client_secret,
            scope=self.config.ccp_oauth_scope,
        )
        return response["access_token"]

    def request(self, method, url, *args, **kwargs):
        url = self._join_url(url)
        return super().request(method, url, *args, **kwargs)

    def prepare_request(self, request, *args, **kwargs):
        request.url = self._join_url(request.url)

        return super().prepare_request(request, *args, **kwargs)

    def _join_url(self, url):
        url = url[1:] if url[0] == "/" else url
        return urljoin(self.base_url, url)

    def onboard_customer(self, payload):
        """
        Onboard a customer using the CCP API.

        :param payload: The payload for CCP onboarding.
        :return: The response from the API.
        """
        response = self.post(url="/services/aws-essentials/customer?api-version=v2", json=payload)
        response.raise_for_status()
        return response.json()

    def get_onboard_status(self, ccp_engagement_id):
        """
        Get the status of the onboarding process.

        :param ccp_engagement_id: The engagement ID for the onboarding process.
        :return: The response from the API.
        """

        response = self.get(
            url=f"services/aws-essentials/customer/engagement/{ccp_engagement_id}?api-version=v2"
        )
        return response.json()
