from abc import ABC

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

    @property
    def item_sku(self):
        """Return the item SKU associated with this processor."""
        return ItemSkusEnum.AWS_USAGE.value

    @property
    def metric_id(self):
        """Return the metric ID associated with this processor."""
        return UsageMetricTypeEnum.USAGE.value


class GenerateUsageIncentivateJournalLines(GenerateUsageDiscountJournalLines):
    """Generate journal lines for AWS usage incentivate metrics."""

    @property
    def item_sku(self):
        """Return the item SKU associated with this processor."""
        return ItemSkusEnum.AWS_USAGE_INCENTIVATE.value

    @property
    def metric_id(self):
        """Return the metric ID associated with this processor."""
        return UsageMetricTypeEnum.USAGE.value


class GenerateUpfrontJournalLines(GenerateUsageDiscountJournalLines):
    """Generate journal lines for AWS upfront/recurring metrics."""

    @property
    def item_sku(self):
        """Return the item SKU associated with this processor."""
        return ItemSkusEnum.UPFRONT.value

    @property
    def metric_id(self):
        """Return the metric ID associated with this processor."""
        return UsageMetricTypeEnum.RECURRING.value


class GenerateUpfrontIncentivateJournalLines(GenerateUsageDiscountJournalLines):
    """Generate journal lines for AWS upfront/recurring incentivate metrics."""

    @property
    def item_sku(self):
        """Return the item SKU associated with this processor."""
        return ItemSkusEnum.UPFRONT_INCENTIVATE.value

    @property
    def metric_id(self):
        """Return the metric ID associated with this processor."""
        return UsageMetricTypeEnum.RECURRING.value
