from dataclasses import asdict
from decimal import Decimal

from swo_aws_extension.constants import BillingJournalUsageSourceEnum
from swo_aws_extension.flows.jobs.billing_journal.models.billing_period import BillingPeriod
from swo_aws_extension.flows.jobs.billing_journal.models.context import BillingJournalContext


def test_initialization() -> None:
    billing_period = BillingPeriod(start_date="2025-10-01", end_date="2025-11-01")

    result = BillingJournalContext(
        mpt_client="mpt_client",
        billing_api_client="billing_client",
        config="config",
        billing_period=billing_period,
        product_ids=["PROD-1"],
        notifier="notifier",
        authorizations=["AUTH-1"],
    )

    expected = {
        "mpt_client": "mpt_client",
        "billing_api_client": "billing_client",
        "config": "config",
        "billing_period": asdict(billing_period),
        "product_ids": ["PROD-1"],
        "notifier": "notifier",
        "authorizations": ["AUTH-1"],
        "pls_charge_percentage": Decimal("5.0"),
        "usage_source": BillingJournalUsageSourceEnum.COST_USAGE_REPORT,
        "dry_run": False,
    }
    assert asdict(result) == expected


def test_authorizations_defaults_to_none() -> None:
    billing_period = BillingPeriod(start_date="2025-01-01", end_date="2025-02-01")

    result = BillingJournalContext(
        mpt_client="mock",
        billing_api_client="mock_billing",
        config="mock",
        billing_period=billing_period,
        product_ids=[],
        notifier="mock",
    )

    assert result.authorizations is None
    assert result.pls_charge_percentage == Decimal("5.0")
    assert result.usage_source == BillingJournalUsageSourceEnum.COST_USAGE_REPORT
    assert result.dry_run is False
