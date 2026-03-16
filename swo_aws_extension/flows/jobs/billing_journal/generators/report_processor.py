from decimal import Decimal

from swo_aws_extension.constants import DEC_ZERO


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

    def extract_metrics(self, report: list[dict], key: str) -> dict[str, Decimal]:
        """Extract metrics filtered by key from report."""
        result: dict[str, Decimal] = {}
        for result_by_time in report:
            for group in result_by_time.get("Groups", []):
                keys = group.get("Keys", [])
                if key not in keys:
                    continue
                amount = self.parse_amount(
                    group.get("Metrics", {}).get("UnblendedCost", {}).get("Amount", "0")
                )
                if amount != Decimal(0):
                    result[keys[1]] = amount
        return result

    def extract_all_metrics_by_record_type(
        self, record_type_report: list[dict]
    ) -> dict[str, dict[str, Decimal]]:
        """Extract all metrics from report, organizing by record type dynamically."""
        result: dict[str, dict[str, Decimal]] = {}

        for result_by_time in record_type_report:
            for group in result_by_time.get("Groups", []):
                self._process_metric_group(group, result)

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

    def _process_metric_group(
        self,
        group: dict,
        result: dict[str, dict[str, Decimal]],
    ) -> None:
        parsed = self.parse_group_metrics(group)
        if parsed:
            record_type, service_name, amount = parsed
            result.setdefault(record_type, {})[service_name] = amount
