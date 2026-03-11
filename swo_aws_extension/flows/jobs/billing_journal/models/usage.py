from dataclasses import dataclass, field
from decimal import Decimal

type AccountDataAlias = dict[str, list[dict]]


@dataclass
class ServiceUsage:
    """Usage details and cost metrics for a single AWS Service."""

    marketplace: Decimal = field(default_factory=lambda: Decimal(0))
    service_invoice_entity: str | None = None
    usage: Decimal = field(default_factory=lambda: Decimal(0))
    support: Decimal = field(default_factory=lambda: Decimal(0))
    refund: Decimal = field(default_factory=lambda: Decimal(0))
    saving_plans: Decimal = field(default_factory=lambda: Decimal(0))
    provider_discount: Decimal = field(default_factory=lambda: Decimal(0))
    recurring: Decimal = field(default_factory=lambda: Decimal(0))


@dataclass
class AccountUsage:
    """Processed metrics ready to generate billing Journal Lines."""

    services: dict[str, ServiceUsage] = field(default_factory=dict)


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
