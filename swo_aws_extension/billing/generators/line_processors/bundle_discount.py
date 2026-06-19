from swo_aws_extension.billing.generators.line_processors.base import (
    JournalLineProcessor,
)

BUNDLE_DISCOUNT_PREFIX = "Bundled_Discount_"


class BundleDiscountJournalLineProcessor(JournalLineProcessor):
    """Generates journal lines for Bundle Discount metrics.

    Always generates a line with the Bundled_Discount_ prefix.
    """

    def __init__(self) -> None:
        super().__init__(prefix_name=BUNDLE_DISCOUNT_PREFIX)
