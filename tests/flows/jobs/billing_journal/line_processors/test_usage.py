from decimal import Decimal

from swo_aws_extension.constants import ItemSkusEnum
from swo_aws_extension.flows.jobs.billing_journal.line_processors.usage import (
    GenerateUpfrontIncentivateJournalLines,
    GenerateUpfrontJournalLines,
    GenerateUsageIncentivateJournalLines,
    GenerateUsageJournalLines,
)


def test_generate_usage_journal_lines_process(config, mock_journal_args, mock_journal_line_factory):
    processor = GenerateUsageJournalLines(
        billing_discount_tolerance_rate=config.billing_discount_tolerance_rate,
        discount=config.billing_discount_base,
    )
    args = mock_journal_args()
    service_name = "Usage service"

    journal_lines = processor.process(**args)

    expected = mock_journal_line_factory(
        service_name=service_name,
        item_external_id=ItemSkusEnum.AWS_USAGE.value,
        price=Decimal(100),
    )
    assert journal_lines == [expected]


def test_generate_usage_incentivate_lines(config, mock_journal_args, mock_journal_line_factory):
    processor = GenerateUsageIncentivateJournalLines(
        billing_discount_tolerance_rate=config.billing_discount_tolerance_rate,
        discount=config.billing_discount_incentivate,
    )
    args = mock_journal_args()
    service_name = "Usage service incentivate"

    journal_lines = processor.process(**args)

    expected = mock_journal_line_factory(
        service_name=service_name,
        item_external_id=ItemSkusEnum.AWS_USAGE_INCENTIVATE.value,
        price=Decimal(100),
    )
    assert journal_lines == [expected]


def test_generate_upfront_journal_lines_process(
    config, mock_journal_args, mock_journal_line_factory
):
    processor = GenerateUpfrontJournalLines(
        billing_discount_tolerance_rate=config.billing_discount_tolerance_rate,
        discount=config.billing_discount_base,
    )
    args = mock_journal_args()
    service_name = "Upfront service"

    journal_lines = processor.process(**args)

    expected = mock_journal_line_factory(
        service_name=service_name,
        item_external_id=ItemSkusEnum.UPFRONT.value,
        price=Decimal(100),
    )
    assert journal_lines == [expected]


def test_generate_upfront_incentivate_lines(config, mock_journal_args, mock_journal_line_factory):
    processor = GenerateUpfrontIncentivateJournalLines(
        billing_discount_tolerance_rate=config.billing_discount_tolerance_rate,
        discount=config.billing_discount_incentivate,
    )
    args = mock_journal_args()
    service_name = "Upfront service incentivate"

    journal_lines = processor.process(**args)

    expected = mock_journal_line_factory(
        service_name=service_name,
        item_external_id=ItemSkusEnum.UPFRONT_INCENTIVATE.value,
        price=Decimal(100),
    )
    assert journal_lines == [expected]
