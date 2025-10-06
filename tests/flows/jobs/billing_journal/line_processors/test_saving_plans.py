from decimal import Decimal

from swo_aws_extension.constants import ItemSkusEnum, UsageMetricTypeEnum
from swo_aws_extension.flows.jobs.billing_journal.line_processors.saving_plans import (
    GenerateSavingPlansIncentivateJournalLines,
    GenerateSavingPlansJournalLines,
)


def test_generate_saving_plans_journal_lines(config, mock_journal_args, mock_journal_line_factory):
    processor = GenerateSavingPlansJournalLines(
        billing_discount_tolerance_rate=config.billing_discount_tolerance_rate,
        discount=config.billing_discount_base,
    )
    args = mock_journal_args()
    service_name = "Saving plan service"
    args["account_metrics"][UsageMetricTypeEnum.SAVING_PLANS.value] = {service_name: 100.0}
    args["account_metrics"][UsageMetricTypeEnum.PROVIDER_DISCOUNT.value] = {service_name: 7.0}

    journal_lines = processor.process(**args)

    expected = mock_journal_line_factory(
        service_name=service_name,
        item_external_id=ItemSkusEnum.SAVING_PLANS_RECURRING_FEE.value,
        price=Decimal(100),
    )
    assert journal_lines == [expected]


def test_generate_saving_plans_incentivate(config, mock_journal_args, mock_journal_line_factory):
    processor = GenerateSavingPlansIncentivateJournalLines(
        billing_discount_tolerance_rate=config.billing_discount_tolerance_rate,
        discount=config.billing_discount_incentivate,
    )
    args = mock_journal_args()
    service_name = "Saving plan service incentivate"
    args["account_metrics"][UsageMetricTypeEnum.SAVING_PLANS.value] = {service_name: 100.0}
    args["account_metrics"][UsageMetricTypeEnum.PROVIDER_DISCOUNT.value] = {service_name: 12.0}

    journal_lines = processor.process(**args)

    expected = mock_journal_line_factory(
        service_name=service_name,
        item_external_id=ItemSkusEnum.SAVING_PLANS_RECURRING_FEE_INCENTIVATE.value,
        price=Decimal(100),
    )
    assert journal_lines == [expected]
