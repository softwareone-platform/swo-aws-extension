from swo_aws_extension.constants import UsageMetricTypeEnum
from swo_aws_extension.flows.jobs.billing_journal.line_processors.base_processor import (
    GenerateItemJournalLines,
)
from swo_aws_extension.flows.jobs.billing_journal.line_validators.discount_validators import (
    DefaultTrueDiscountValidator,
)


class ErrorJournalLinesProcessor(GenerateItemJournalLines):
    """Processor for services not handled by any other processor."""

    _validator = DefaultTrueDiscountValidator
    _dynamic_metric_ids = (
        UsageMetricTypeEnum.USAGE,
        UsageMetricTypeEnum.SUPPORT,
        UsageMetricTypeEnum.MARKETPLACE,
        UsageMetricTypeEnum.SAVING_PLANS,
        UsageMetricTypeEnum.RECURRING,
    )

    def __init__(self, billing_discount_tolerance_rate, discount=None, exclude_services=None):
        # TODO: Overridden __init__ to pass the extra parameter `exclude_services` to provide
        #  the list of already processed services. This allows calculation of unprocessed lines
        #  and marking them as errors. This should be refactored later to avoid modifying the
        #  class constructor.
        super().__init__(billing_discount_tolerance_rate, discount)
        self._exclude_services = () if exclude_services is None else exclude_services

    @property
    def item_sku(self):
        """Return the item SKU associated with this processor."""
        return ""

    @property
    def metric_id(self):
        """Return the metric ID associated with this processor."""
        return ""
