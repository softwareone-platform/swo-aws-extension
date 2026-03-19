from dataclasses import dataclass
from typing import Any

from swo_aws_extension.flows.jobs.billing_journal.models.billing_period import BillingPeriod
from swo_aws_extension.flows.jobs.billing_journal.models.invoice import OrganizationInvoice
from swo_aws_extension.flows.jobs.billing_journal.models.journal_line import JournalDetails
from swo_aws_extension.flows.jobs.billing_journal.models.usage import AccountUsage


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


@dataclass
class LineProcessorContext:
    """Context passed to line processors during journal line generation."""

    account_id: str
    account_usage: AccountUsage
    journal_details: JournalDetails
    organization_invoice: OrganizationInvoice
