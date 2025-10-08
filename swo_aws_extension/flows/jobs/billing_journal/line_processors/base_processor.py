from abc import ABC, abstractmethod

from swo_aws_extension.constants import UsageMetricTypeEnum
from swo_aws_extension.flows.jobs.billing_journal.invoice_details import InvoiceDetails
from swo_aws_extension.flows.jobs.billing_journal.models import (
    JournalLine,
)


class GenerateItemJournalLines(ABC):
    """Base class for generating journal lines for different AWS billing items."""

    _validator = None
    _exclude_services = ()
    _dynamic_exclude_services = ()
    _dynamic_metric_ids = ()

    def __init__(self, billing_discount_tolerance_rate, discount=None):
        self._billing_discount_tolerance_rate = billing_discount_tolerance_rate
        self._discount = discount

    @property
    @abstractmethod
    def item_sku(self):
        """Return the item SKU associated with this processor."""
        raise NotImplementedError

    @property
    @abstractmethod
    def metric_id(self):
        """Return the metric ID associated with this processor."""
        raise NotImplementedError

    def can_process(self, item_sku):
        """Check if the processor can handle the given item SKU.

        Args:
            item_sku (str): The item SKU to check.

        Returns:
            bool: True if the processor can handle the item SKU, False otherwise.
        """
        return item_sku == self.item_sku

    def process(self, account_id, account_metrics, journal_details, account_invoices):
        """Generate item journal lines."""
        journal_lines = []
        for service_name, amount in self._get_metric_data(account_metrics):
            if not self._validator().validate(
                self._discount,
                amount,
                service_name,
                account_metrics,
                self._billing_discount_tolerance_rate,
            ):
                continue

            invoice_details = InvoiceDetails(
                self.item_sku,
                service_name,
                amount,
                account_id,
                account_invoices,
                account_metrics.get(UsageMetricTypeEnum.SERVICE_INVOICE_ENTITY.value, {}).get(
                    service_name, ""
                ),
                account_metrics.get(UsageMetricTypeEnum.PROVIDER_DISCOUNT.value, {}).get(
                    service_name, 0
                ),
            )

            journal_lines.append(JournalLine.build(self.item_sku, journal_details, invoice_details))
        return journal_lines

    def _get_exclude_services(self, account_metrics):
        exclude_services = self._exclude_services
        if not self._dynamic_exclude_services:
            return exclude_services
        for dynamic_exclude_service in self._dynamic_exclude_services:
            dynamic_exclude_services = account_metrics.get(dynamic_exclude_service, {}).keys()
            exclude_services += tuple(dynamic_exclude_services)
        return exclude_services

    def _get_metric_data(self, account_metrics):
        metric_data = account_metrics.get(self.metric_id, {}).copy()
        if self._dynamic_metric_ids:
            for dynamic_metric_id in self._dynamic_metric_ids:
                metric_data.update(account_metrics.get(dynamic_metric_id, {}))

        filtered_metrics = {
            service_name: amount
            for service_name, amount in metric_data.items()
            if service_name not in self._get_exclude_services(account_metrics)
        }
        return filtered_metrics.items()
