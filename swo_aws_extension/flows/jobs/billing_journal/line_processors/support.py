from swo_aws_extension.constants import ItemSkusEnum, UsageMetricTypeEnum
from swo_aws_extension.flows.jobs.billing_journal.line_processors.base_processor import (
    GenerateItemJournalLines,
)
from swo_aws_extension.flows.jobs.billing_journal.line_validators.discount_validators import (
    DefaultTrueDiscountValidator,
    SupportDiscountValidator,
)


class GenerateSupportJournalLines(GenerateItemJournalLines):
    """Generate journal lines for AWS support usage metrics."""

    _validator = SupportDiscountValidator

    @property
    def item_sku(self):
        """Return the item SKU associated with this processor."""
        return ItemSkusEnum.AWS_SUPPORT.value

    @property
    def metric_id(self):
        """Return the metric ID associated with this processor."""
        return UsageMetricTypeEnum.SUPPORT.value


class GenerateSupportEnterpriseJournalLines(GenerateItemJournalLines):
    """Generate journal lines for AWS enterprise support usage metrics."""

    _validator = SupportDiscountValidator

    @property
    def item_sku(self):
        """Return the item SKU associated with this processor."""
        return ItemSkusEnum.AWS_SUPPORT_ENTERPRISE.value

    @property
    def metric_id(self):
        """Return the metric ID associated with this processor."""
        return UsageMetricTypeEnum.SUPPORT.value


class GenerateSupportDevelopmentJournalLines(GenerateItemJournalLines):
    """Generate journal lines for AWS Development support usage metrics."""

    _validator = DefaultTrueDiscountValidator

    @property
    def item_sku(self):
        """Return the item SKU associated with this processor."""
        return ItemSkusEnum.AWS_OTHER_SERVICES.value

    @property
    def metric_id(self):
        """Return the metric ID associated with this processor."""
        return UsageMetricTypeEnum.SUPPORT.value
