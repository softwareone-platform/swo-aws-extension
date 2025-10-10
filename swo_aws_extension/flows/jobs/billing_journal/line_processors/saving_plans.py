from typing import override

from swo_aws_extension.constants import ItemSkusEnum, UsageMetricTypeEnum
from swo_aws_extension.flows.jobs.billing_journal.line_processors.base_processor import (
    GenerateItemJournalLines,
)
from swo_aws_extension.flows.jobs.billing_journal.line_validators.discount_validators import (
    DefaultDiscountValidator,
)


class GenerateSavingPlansJournalLines(GenerateItemJournalLines):
    """Generate journal lines for AWS saving plans recurring fee metrics."""

    _validator = DefaultDiscountValidator

    @override
    @property
    def item_sku(self):
        return ItemSkusEnum.SAVING_PLANS_RECURRING_FEE.value

    @override
    @property
    def metric_id(self):
        return UsageMetricTypeEnum.SAVING_PLANS.value


class GenerateSavingPlansIncentivateJournalLines(GenerateItemJournalLines):
    """Generate journal lines for AWS saving plans recurring fee incentivate metrics."""

    _validator = DefaultDiscountValidator
    _exclude_services = ()

    @override
    @property
    def item_sku(self):
        return ItemSkusEnum.SAVING_PLANS_RECURRING_FEE_INCENTIVATE.value

    @override
    @property
    def metric_id(self):
        return UsageMetricTypeEnum.SAVING_PLANS.value
