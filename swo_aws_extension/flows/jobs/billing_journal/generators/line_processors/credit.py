from typing import override

from swo_aws_extension.constants import DEC_ZERO, AWSRecordTypeEnum
from swo_aws_extension.flows.jobs.billing_journal.generators.line_processors.base import (
    LineProcessor,
)
from swo_aws_extension.flows.jobs.billing_journal.models.context import LineProcessorContext
from swo_aws_extension.flows.jobs.billing_journal.models.journal_line import JournalLine
from swo_aws_extension.flows.jobs.billing_journal.models.usage import AccountUsage, ServiceMetric

CREDIT_PREFIX = "CREDIT - "
SPP_PREFIX = "SPP - "
SPP_SUFFIX = (
    " - Invoice amount is 0 with credits applied. The SPP value will not be "
    "charged to the customer."
)


class CreditLineProcessor(LineProcessor):
    """Generates journal lines for Credit metrics.

    Always generates a credit line with the CREDIT prefix. When the principal invoice amount is
    zero, also generates an SPP discount line to return the SPP provider benefit to the customer.
    """

    def __init__(self) -> None:
        super().__init__(prefix_name=CREDIT_PREFIX)
        self._spp_processor = LineProcessor(
            prefix_name=SPP_PREFIX,
            suffix_name=SPP_SUFFIX,
        )

    @override
    def process(
        self,
        metric: ServiceMetric,
        context: LineProcessorContext,
    ) -> list[JournalLine]:
        lines = super().process(metric, context)
        if not lines:
            return lines

        if self._should_add_spp_line(context):
            spp_metric = self._find_spp_for_service(
                context.account_usage,
                metric.service_name,
            )
            if spp_metric:
                lines.extend(self._spp_processor.process(spp_metric, context))

        return lines

    def _should_add_spp_line(self, context: LineProcessorContext) -> bool:
        principal_amount = context.organization_invoice.principal_invoice_amount
        return principal_amount is None or principal_amount == DEC_ZERO

    def _find_spp_for_service(
        self,
        account_usage: AccountUsage,
        service_name: str,
    ) -> ServiceMetric | None:
        spp_metrics = [
            metric
            for metric in account_usage.get_metrics_by_service(service_name)
            if metric.record_type == AWSRecordTypeEnum.SOLUTION_PROVIDER_PROGRAM_DISCOUNT
        ]
        return spp_metrics[0] if spp_metrics else None
