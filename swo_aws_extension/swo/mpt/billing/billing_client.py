from swo_aws_extension.swo.mpt.billing.journal_client import JournalClient

# TODO: SDK candidate


class BillingClient:
    """Billing client for MPT API."""

    def __init__(self, client):
        self._client = client
        self.journal = JournalClient(client)
