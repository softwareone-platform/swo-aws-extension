from decimal import Decimal

from swo_aws_extension.constants import ItemSkusEnum, UsageMetricTypeEnum
from swo_aws_extension.flows.jobs.billing_journal.line_processors.support import (
    GenerateSupportDevelopmentJournalLines,
    GenerateSupportEnterpriseJournalLines,
    GenerateSupportJournalLines,
)


def test_generate_support_business_lines(config, mock_journal_args, mock_journal_line_factory):
    processor = GenerateSupportJournalLines(
        billing_discount_tolerance_rate=config.billing_discount_tolerance_rate,
        discount=config.billing_discount_base,
    )
    args = mock_journal_args()
    service_name = "AWS Support (Business)"
    args["account_metrics"][UsageMetricTypeEnum.SUPPORT.value] = {service_name: 100.0}
    args["account_metrics"][UsageMetricTypeEnum.PROVIDER_DISCOUNT.value] = {service_name: 7.0}

    journal_lines = processor.process(**args)

    expected = mock_journal_line_factory(
        service_name=service_name,
        item_external_id=ItemSkusEnum.AWS_SUPPORT.value,
        price=Decimal(100),
    )
    assert journal_lines == [expected]


def test_generate_support_enterprise_lines(config, mock_journal_args, mock_journal_line_factory):
    processor = GenerateSupportEnterpriseJournalLines(
        billing_discount_tolerance_rate=config.billing_discount_tolerance_rate,
        discount=config.billing_discount_support_enterprise,
    )
    args = mock_journal_args()
    service_name = "AWS Support (Enterprise)"
    args["account_metrics"][UsageMetricTypeEnum.SUPPORT.value] = {service_name: 100.0}
    args["account_metrics"][UsageMetricTypeEnum.PROVIDER_DISCOUNT.value] = {service_name: 35.0}

    journal_lines = processor.process(**args)

    expected = mock_journal_line_factory(
        service_name=service_name,
        item_external_id=ItemSkusEnum.AWS_SUPPORT_ENTERPRISE.value,
        price=Decimal(100),
    )
    assert journal_lines == [expected]


def test_generate_support_development_lines(config, mock_journal_args, mock_journal_line_factory):
    processor = GenerateSupportDevelopmentJournalLines(
        billing_discount_tolerance_rate=config.billing_discount_tolerance_rate, discount=0
    )
    args = mock_journal_args()
    service_name = "AWS Support (Development)"
    args["account_metrics"][UsageMetricTypeEnum.SUPPORT.value] = {service_name: 100}
    args["account_metrics"][UsageMetricTypeEnum.PROVIDER_DISCOUNT.value] = {service_name: 0}

    journal_lines = processor.process(**args)

    expected = mock_journal_line_factory(
        service_name=service_name,
        item_external_id=ItemSkusEnum.AWS_OTHER_SERVICES.value,
        price=Decimal(100),
    )
    assert journal_lines == [expected]
