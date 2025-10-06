from swo_aws_extension.constants import AWSServiceEnum, ItemSkusEnum, UsageMetricTypeEnum
from swo_aws_extension.flows.jobs.billing_journal.line_processors.base_processor import (
    GenerateItemJournalLines,
)
from swo_aws_extension.flows.jobs.billing_journal.line_validators.discount_validators import (
    DefaultTrueDiscountValidator,
)


class GenerateMarketplaceJournalLines(GenerateItemJournalLines):
    """Generate journal lines for AWS Marketplace usage metrics."""

    _exclude_services = (AWSServiceEnum.TAX.value,)
    _validator = DefaultTrueDiscountValidator

    @property
    def item_sku(self):
        """Return the item SKU associated with this processor."""
        return ItemSkusEnum.AWS_MARKETPLACE.value

    @property
    def metric_id(self):
        """Return the metric ID associated with this processor."""
        return UsageMetricTypeEnum.MARKETPLACE.value
