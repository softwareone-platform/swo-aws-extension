from swo_aws_extension.swo.mpt.billing.billing_client import BillingClient
from swo_aws_extension.swo.mpt.billing.journal_client import JournalClient


def test_billing_client_init(mpt_client):
    client = mpt_client

    result = BillingClient(client)

    assert isinstance(result, BillingClient)
    assert hasattr(result, "journal")
    assert isinstance(result.journal, JournalClient)
