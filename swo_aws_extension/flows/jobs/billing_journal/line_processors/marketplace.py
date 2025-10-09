from typing import override

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

    @override
    @property
    def item_sku(self):
        return ItemSkusEnum.AWS_MARKETPLACE.value

    @override
    @property
    def metric_id(self):
        return UsageMetricTypeEnum.MARKETPLACE.value
