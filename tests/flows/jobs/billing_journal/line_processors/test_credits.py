from decimal import Decimal

from swo_aws_extension.constants import ItemSkusEnum, UsageMetricTypeEnum
from swo_aws_extension.flows.jobs.billing_journal.line_processors.credits import (
    GenerateCreditProviderDiscountJournalLines,
    GenerateCreditsJournalLines,
)


def test_generate_credits_lines(config, mock_journal_args, mock_journal_line_factory):
    processor = GenerateCreditsJournalLines(
        billing_discount_tolerance_rate=config.billing_discount_tolerance_rate, discount=0
    )
    args = mock_journal_args()
    service_name = "Other AWS services"
    args["account_metrics"][UsageMetricTypeEnum.CREDITS.value] = {service_name: Decimal("100.0")}

    journal_lines = processor.process(**args)

    expected = mock_journal_line_factory(
        service_name=f"CREDIT - {service_name}",
        item_external_id=ItemSkusEnum.AWS_OTHER_SERVICES.value,
        price=Decimal("100.0"),
    )
    assert journal_lines == [expected]


def test_generate_credit_provider_discount_lines(
    config, mock_journal_args, mock_journal_line_factory
):
    processor = GenerateCreditProviderDiscountJournalLines(
        billing_discount_tolerance_rate=config.billing_discount_tolerance_rate, discount=0
    )
    args = mock_journal_args()
    args["account_metrics"][UsageMetricTypeEnum.CREDITS_PROVIDER_DISCOUNT.value] = {
        "Other AWS services": Decimal("100.0")
    }

    journal_lines = processor.process(**args)

    suffix = (
        " - Invoice amount is 0 with credits applied. The SPP value will not be "
        "charged to the customer."
    )
    expected = mock_journal_line_factory(
        service_name=f"SPP - Other AWS services{suffix}",
        item_external_id=ItemSkusEnum.AWS_OTHER_SERVICES.value,
        price=Decimal("100.0"),
    )
    assert journal_lines == [expected]
