from dataclasses import dataclass
from typing import Any

from swo_aws_extension.flows.jobs.billing_journal.models.billing_period import BillingPeriod


@dataclass
class BillingJournalContext:
    """Context holding necessary components for billing journal generation."""

    mpt_client: Any
    billing_api_client: Any
    config: Any
    billing_period: BillingPeriod
    product_ids: list[str]
    notifier: Any
    authorizations: list[str] | None = None
