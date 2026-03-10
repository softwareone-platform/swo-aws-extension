from dataclasses import asdict

from swo_aws_extension.flows.jobs.billing_journal.models.billing_period import BillingPeriod
from swo_aws_extension.flows.jobs.billing_journal.models.context import BillingJournalContext


def test_initialization():
    billing_period = BillingPeriod(start_date="2025-10-01", end_date="2025-11-01")

    result = BillingJournalContext(
        mpt_client="mpt_client",
        config="config",
        billing_period=billing_period,
        product_ids=["PROD-1"],
        notifier="notifier",
        authorizations=["AUTH-1"],
    )

    expected = {
        "mpt_client": "mpt_client",
        "config": "config",
        "billing_period": asdict(billing_period),
        "product_ids": ["PROD-1"],
        "notifier": "notifier",
        "authorizations": ["AUTH-1"],
    }
    assert asdict(result) == expected


def test_authorizations_defaults_to_none():
    billing_period = BillingPeriod(start_date="2025-01-01", end_date="2025-02-01")

    result = BillingJournalContext(
        mpt_client="mock",
        config="mock",
        billing_period=billing_period,
        product_ids=[],
        notifier="mock",
    )

    assert result.authorizations is None
