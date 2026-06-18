from dataclasses import dataclass, field
from decimal import Decimal

type AccountDataAlias = dict[str, list[dict]]


@dataclass
class ExtractedMetric:
    """A single dynamically extracted metric from Cost Explorer raw output."""

    service_name: str
    amount: Decimal
    start_date: str
    end_date: str
    record_type: str | None = None


@dataclass
class ServiceMetric:
    """A single cost metric for a service (e.g., usage, support, refund, etc.)."""

    service_name: str
    record_type: str
    amount: Decimal = field(default_factory=lambda: Decimal(0))
    invoice_entity: str | None = None
    invoice_id: str | None = None
    start_date: str | None = None
    end_date: str | None = None


@dataclass
class AccountUsage:
    """Processed metrics ready to generate billing Journal Lines."""

    metrics: list[ServiceMetric] = field(default_factory=list)

    def add_metric(self, metric: ServiceMetric) -> None:
        """Add a metric to the account usage."""
        self.metrics.append(metric)

    def get_metrics_by_record_type(self, record_type: str) -> list[ServiceMetric]:
        """Get all metrics for a specific record type."""
        return [metric for metric in self.metrics if metric.record_type == record_type]

    def get_metrics_by_service(self, service_name: str) -> list[ServiceMetric]:
        """Get all metrics for a specific service."""
        return [metric for metric in self.metrics if metric.service_name == service_name]


@dataclass
class OrganizationReport:
    """Contains the original AWS structure (RAW dictionaries/responses) unified."""

    organization_data: dict[str, list[dict]] = field(default_factory=dict)
    accounts_data: dict[str, AccountDataAlias] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert the full structure into a dictionary."""
        return {
            "organization_data": self.organization_data,
            "accounts_data": self.accounts_data,
        }


@dataclass
class OrganizationUsageResult:
    """Global container returned by the generator, includes raw and processed data."""

    reports: OrganizationReport
    usage_by_account: dict[str, AccountUsage] = field(default_factory=dict)

    def has_enterprise_support(self) -> bool:
        """Check if any account has 'AWS Support (Enterprise)' in its metrics."""
        return any(
            account.get_metrics_by_service("AWS Support (Enterprise)")
            for account in self.usage_by_account.values()
        )
