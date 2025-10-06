from swo_aws_extension.constants import AWSServiceEnum, ItemSkusEnum, UsageMetricTypeEnum
from swo_aws_extension.flows.jobs.billing_journal.line_processors.base_processor import (
    GenerateItemJournalLines,
)
from swo_aws_extension.flows.jobs.billing_journal.line_validators.discount_validators import (
    DefaultDiscountValidator,
)


class GenerateOtherServicesJournalLines(GenerateItemJournalLines):
    """Generate journal lines for other AWS services excluding usage and marketplace services."""

    _exclude_services = (
        AWSServiceEnum.TAX.value,
        AWSServiceEnum.REFUND.value,
        AWSServiceEnum.SAVINGS_PLANS_FOR_AWS_COMPUTE_USAGE.value,
    )
    _dynamic_exclude_services = (UsageMetricTypeEnum.MARKETPLACE.value,)
    _validator = DefaultDiscountValidator

    @property
    def item_sku(self):
        """Return the item SKU associated with this processor."""
        return ItemSkusEnum.AWS_OTHER_SERVICES.value

    @property
    def metric_id(self):
        """Return the metric ID associated with this processor."""
        return UsageMetricTypeEnum.USAGE.value
