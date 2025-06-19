from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_mpt_api.billing import BillingClient


class MPTAPIClient:
    def __init__(self, client: MPTClient):
        self._client = client
        self.billing = BillingClient(client)
