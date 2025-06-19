from swo_mpt_api.billing.journal_client import JournalClient


class BillingClient:
    def __init__(self, client):
        self._client = client
        self.journal = JournalClient(client)
