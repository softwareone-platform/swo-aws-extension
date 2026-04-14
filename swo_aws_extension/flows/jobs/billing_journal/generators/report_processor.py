from decimal import Decimal

from swo_aws_extension.constants import DEC_ZERO
from swo_aws_extension.flows.jobs.billing_journal.models.usage import ExtractedMetric


def _get_time_period(result_by_time: dict) -> tuple[str, str]:
    """Extract start and end date from a time period."""
    time_period = result_by_time.get("TimePeriod", {})
    return time_period.get("Start", ""), time_period.get("End", "")


class ReportProcessor:
    """Processes AWS Cost Explorer reports to extract metrics."""

    def extract_invoice_entities(self, report: list[dict]) -> dict[str, str]:
        """Extract service to invoice entity mapping from report."""
        result: dict[str, str] = {}
        for result_by_time in report:
            for group in result_by_time.get("Groups", []):
                keys = group.get("Keys", [])
                if len(keys) >= 2:
                    result[keys[0]] = keys[1]
        return result

    def extract_metrics(self, report: list[dict], key: str) -> list[ExtractedMetric]:
        """Extract metrics filtered by key from report."""
        result: list[ExtractedMetric] = []
        for result_by_time in report:
            start_date, end_date = _get_time_period(result_by_time)
            for group in result_by_time.get("Groups", []):
                self._conditional_append_metric(group, key, start_date, end_date, result)
        return result

    def extract_all_metrics_by_record_type(
        self, record_type_report: list[dict]
    ) -> list[ExtractedMetric]:
        """Extract all metrics from report, organizing by record type dynamically."""
        result: list[ExtractedMetric] = []

        for result_by_time in record_type_report:
            start_date, end_date = _get_time_period(result_by_time)
            for group in result_by_time.get("Groups", []):
                self._process_metric_group(group, result, start_date, end_date)

        return result

    def parse_group_metrics(self, group: dict) -> tuple[str, str, Decimal] | None:
        """Parse metrics from a cost explorer group."""
        keys = group.get("Keys", [])
        if len(keys) < 2:
            return None

        record_type = keys[0]
        service_name = keys[1]
        amount = self.parse_amount(
            group.get("Metrics", {}).get("UnblendedCost", {}).get("Amount", "0")
        )

        if amount == DEC_ZERO:
            return None

        return record_type, service_name, amount

    def parse_amount(self, amount: str) -> Decimal:
        """Convert a string amount to Decimal, handling comma and dot separators."""
        return Decimal(amount.replace(",", ".") if "," in amount else amount)

    def _conditional_append_metric(
        self,
        group: dict,
        key: str,
        start_date: str,
        end_date: str,
        result: list[ExtractedMetric],
    ) -> None:
        keys = group.get("Keys", [])
        if key not in keys:
            return

        amount = self.parse_amount(
            group.get("Metrics", {}).get("UnblendedCost", {}).get("Amount", "0")
        )
        if amount != Decimal(0):
            result.append(
                ExtractedMetric(
                    service_name=keys[1],
                    amount=amount,
                    start_date=start_date,
                    end_date=end_date,
                )
            )

    def _process_metric_group(
        self,
        group: dict,
        result: list[ExtractedMetric],
        start_date: str,
        end_date: str,
    ) -> None:
        parsed = self.parse_group_metrics(group)
        if parsed:
            record_type, service_name, amount = parsed
            result.append(
                ExtractedMetric(
                    service_name=service_name,
                    amount=amount,
                    start_date=start_date,
                    end_date=end_date,
                    record_type=record_type,
                )
            )
