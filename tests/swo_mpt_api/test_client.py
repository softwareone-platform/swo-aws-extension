from swo_mpt_api import MPTAPIClient
from swo_mpt_api.billing import BillingClient


def test_mpt_api_client(mpt_client):
    api = MPTAPIClient(mpt_client)

    assert isinstance(api, MPTAPIClient)
    assert hasattr(api, "billing")
    assert isinstance(api.billing, BillingClient)
