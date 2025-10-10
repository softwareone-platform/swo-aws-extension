from decimal import Decimal

from swo_aws_extension.constants import ItemSkusEnum
from swo_aws_extension.flows.jobs.billing_journal.line_processors.marketplace import (
    GenerateMarketplaceJournalLines,
)


def test_generate_marketplace_journal_lines(mock_journal_args, mock_journal_line_factory):
    processor = GenerateMarketplaceJournalLines(billing_discount_tolerance_rate=1, discount=0)
    item_external_id = ItemSkusEnum.AWS_MARKETPLACE.value
    args = mock_journal_args()

    journal_lines = processor.process(**args)

    expected = mock_journal_line_factory(
        service_name="Marketplace service",
        item_external_id=item_external_id,
        price=Decimal(100),
    )
    assert journal_lines == [expected]
