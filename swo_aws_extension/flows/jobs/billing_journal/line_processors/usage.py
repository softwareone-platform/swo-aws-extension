from abc import ABC
from typing import override

from swo_aws_extension.constants import AWSServiceEnum, ItemSkusEnum, UsageMetricTypeEnum
from swo_aws_extension.flows.jobs.billing_journal.line_processors.base_processor import (
    GenerateItemJournalLines,
)
from swo_aws_extension.flows.jobs.billing_journal.line_validators.discount_validators import (
    UsageDiscountValidator,
)


class GenerateUsageDiscountJournalLines(GenerateItemJournalLines, ABC):
    """Base class for generating journal lines for AWS usage and recurring metrics."""

    _validator = UsageDiscountValidator
    _exclude_services = (AWSServiceEnum.SAVINGS_PLANS_FOR_AWS_COMPUTE_USAGE,)


class GenerateUsageJournalLines(GenerateUsageDiscountJournalLines):
    """Generate journal lines for AWS usage metrics."""

    @override
    @property
    def item_sku(self):
        return ItemSkusEnum.AWS_USAGE.value

    @override
    @property
    def metric_id(self):
        return UsageMetricTypeEnum.USAGE.value


class GenerateUsageIncentivateJournalLines(GenerateUsageDiscountJournalLines):
    """Generate journal lines for AWS usage incentivate metrics."""

    @override
    @property
    def item_sku(self):
        return ItemSkusEnum.AWS_USAGE_INCENTIVATE.value

    @override
    @property
    def metric_id(self):
        return UsageMetricTypeEnum.USAGE.value


class GenerateUpfrontJournalLines(GenerateUsageDiscountJournalLines):
    """Generate journal lines for AWS upfront/recurring metrics."""

    @override
    @property
    def item_sku(self):
        return ItemSkusEnum.UPFRONT.value

    @override
    @property
    def metric_id(self):
        return UsageMetricTypeEnum.RECURRING.value


class GenerateUpfrontIncentivateJournalLines(GenerateUsageDiscountJournalLines):
    """Generate journal lines for AWS upfront/recurring incentivate metrics."""

    @override
    @property
    def item_sku(self):
        return ItemSkusEnum.UPFRONT_INCENTIVATE.value

    @override
    @property
    def metric_id(self):
        return UsageMetricTypeEnum.RECURRING.value
