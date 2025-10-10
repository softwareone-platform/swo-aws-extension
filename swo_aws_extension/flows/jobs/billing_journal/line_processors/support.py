from typing import override

from swo_aws_extension.constants import ItemSkusEnum, UsageMetricTypeEnum
from swo_aws_extension.flows.jobs.billing_journal.line_processors.base_processor import (
    GenerateItemJournalLines,
)
from swo_aws_extension.flows.jobs.billing_journal.line_validators.discount_validators import (
    DefaultDiscountValidator,
    SupportDiscountValidator,
)


class GenerateSupportJournalLines(GenerateItemJournalLines):
    """Generate journal lines for AWS support usage metrics."""

    _validator = SupportDiscountValidator

    @override
    @property
    def item_sku(self):
        return ItemSkusEnum.AWS_SUPPORT.value

    @override
    @property
    def metric_id(self):
        return UsageMetricTypeEnum.SUPPORT.value


class GenerateSupportEnterpriseJournalLines(GenerateItemJournalLines):
    """Generate journal lines for AWS enterprise support usage metrics."""

    _validator = SupportDiscountValidator

    @override
    @property
    def item_sku(self):
        return ItemSkusEnum.AWS_SUPPORT_ENTERPRISE.value

    @override
    @property
    def metric_id(self):
        return UsageMetricTypeEnum.SUPPORT.value


class GenerateSupportDevelopmentJournalLines(GenerateItemJournalLines):
    """Generate journal lines for AWS Development support usage metrics."""

    _validator = DefaultDiscountValidator

    @override
    @property
    def item_sku(self):
        return ItemSkusEnum.AWS_OTHER_SERVICES.value

    @override
    @property
    def metric_id(self):
        return UsageMetricTypeEnum.SUPPORT.value
