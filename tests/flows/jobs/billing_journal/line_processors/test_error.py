from decimal import Decimal

from swo_aws_extension.constants import UsageMetricTypeEnum
from swo_aws_extension.flows.jobs.billing_journal.line_processors.error import (
    ErrorJournalLinesProcessor,
)


def test_error_processor(mock_journal_args, mock_journal_line_factory):
    processor = ErrorJournalLinesProcessor(
        billing_discount_tolerance_rate=1,
        discount=0,
        exclude_services=[
            "Usage service",
            "Usage service incentivate",
            "Other AWS services",
            "AWS Support (Business)",
            "AWS Support (Development)",
            "AWS Support (Enterprise)",
            "Marketplace service",
            "Saving plan service",
            "Saving plan service incentivate",
            "Upfront service",
            "Upfront service incentivate",
            "Tax",
        ],
    )
    args = mock_journal_args()
    args["account_metrics"][UsageMetricTypeEnum.USAGE.value]["Error AWS services"] = 100

    journal_lines = processor.process(**args)

    expected = mock_journal_line_factory(
        service_name="Error AWS services",
        item_external_id="Item Not Found",
        invoice_id=None,
        invoice_entity="",
        price=Decimal(100),
        error="1234567890 - Service Error AWS services with amount 100  and discount 0.0 "
        "did not match any subscription item.",
    )
    assert journal_lines == [expected]
