from typing import override

from swo_aws_extension.constants import ItemSkusEnum, UsageMetricTypeEnum
from swo_aws_extension.flows.jobs.billing_journal.line_processors.base_processor import (
    GenerateItemJournalLines,
)
from swo_aws_extension.flows.jobs.billing_journal.line_validators.discount_validators import (
    DefaultTrueDiscountValidator,
)


class GenerateCreditsJournalLines(GenerateItemJournalLines):
    """Journal lines generator for AWS credits."""

    _validator = DefaultTrueDiscountValidator
    _prefix_name = "CREDIT - "

    @override
    @property
    def item_sku(self):
        return ItemSkusEnum.AWS_OTHER_SERVICES.value

    @override
    @property
    def metric_id(self):
        return UsageMetricTypeEnum.CREDITS.value


class GenerateCreditProviderDiscountJournalLines(GenerateItemJournalLines):
    """Journal lines generator for credit provider discounts."""

    _validator = DefaultTrueDiscountValidator
    _prefix_name = "SPP - "
    _suffix_name = (
        " - Invoice amount is 0 with credits applied. The SPP value will not be "
        "charged to the customer."
    )

    @override
    @property
    def item_sku(self):
        return ItemSkusEnum.AWS_OTHER_SERVICES.value

    @override
    @property
    def metric_id(self):
        return UsageMetricTypeEnum.CREDITS_PROVIDER_DISCOUNT.value
