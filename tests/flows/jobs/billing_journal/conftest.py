from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from swo_aws_extension.constants import BillingJournalUsageSourceEnum
from swo_aws_extension.flows.jobs.billing_journal.journal_manager import JournalManager
from swo_aws_extension.flows.jobs.billing_journal.models.billing_period import BillingPeriod
from swo_aws_extension.flows.jobs.billing_journal.models.context import BillingJournalContext
from swo_aws_extension.flows.jobs.billing_journal.models.journal_line import (
    Description,
    ExternalIds,
    JournalLine,
    Period,
    Price,
)
from swo_aws_extension.flows.jobs.billing_journal.models.search import (
    Search,
    SearchItem,
    SearchSource,
)


@pytest.fixture
def mock_mpt_client():
    return MagicMock()


@pytest.fixture
def mock_billing_client():
    return MagicMock()


@pytest.fixture
def mock_context(mock_mpt_client, mock_billing_client):
    context = MagicMock(spec=BillingJournalContext)
    context.mpt_client = mock_mpt_client
    context.billing_api_client = mock_billing_client
    context.billing_period = BillingPeriod(start_date="2025-10-01", end_date="2025-11-01")
    context.config = MagicMock()
    context.config.mpt_portal_base_url = "https://mpt.test"
    context.notifier = MagicMock()
    context.product_ids = ["PROD-1"]
    context.pls_charge_percentage = Decimal("5.0")
    context.usage_source = BillingJournalUsageSourceEnum.COST_USAGE_REPORT
    return context


@pytest.fixture
def manager(mock_context):
    return JournalManager(mock_context, "AUTH-123")


@pytest.fixture
def sample_journal_line():
    return JournalLine(
        description=Description("Service A", "Account/Entity"),
        external_ids=ExternalIds("INV-1", "AGR-1", "VND-1"),
        period=Period("2025-01-01", "2025-01-31"),
        price=Price(Decimal("10.50"), Decimal("10.50")),
        quantity=2,
        search=Search(
            search_item=SearchItem("item.crit", "ITEM-1"),
            source=SearchSource("Subscription", "source.crit", "SRC-1"),
        ),
        segment="COM",
    )
