from abc import ABC, abstractmethod

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.flows.jobs.billing_journal.models.billing_period import BillingPeriod
from swo_aws_extension.flows.jobs.billing_journal.models.invoice import OrganizationInvoice
from swo_aws_extension.flows.jobs.billing_journal.models.usage import (
    AccountUsage,
    OrganizationReport,
    OrganizationUsageResult,
)


class BaseOrganizationUsageGenerator(ABC):
    """Base interface for extracting organization usage (Cost Explorer, CUR, etc.)."""

    def __init__(self, aws_client: AWSClient) -> None:
        self._aws_client = aws_client
        self._reports = OrganizationReport()
        self._usage_by_account: dict[str, AccountUsage] = {}

    @abstractmethod
    def run(
        self,
        currency: str,
        mpa_account: str,
        billing_period: BillingPeriod,
        organization_invoice: OrganizationInvoice | None = None,
    ) -> OrganizationUsageResult:
        """Extract raw organization usage and convert it into account metrics."""
