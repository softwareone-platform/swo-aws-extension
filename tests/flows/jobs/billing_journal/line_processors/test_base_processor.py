from decimal import Decimal

import pytest

from swo_aws_extension.constants import ItemSkusEnum, UsageMetricTypeEnum
from swo_aws_extension.flows.jobs.billing_journal.line_processors.base_processor import (
    GenerateItemJournalLines,
)


class ValidatorAlwaysTrue:
    def validate(self, discount, amount, service_name, account_metrics, tolerance_rate):
        return True


class ValidatorAlwaysFalse:
    def validate(self, discount, amount, service_name, account_metrics, tolerance_rate):
        return False


class DummyProcessor(GenerateItemJournalLines):
    _validator = ValidatorAlwaysTrue
    _exclude_services = ("Tax",)

    @property
    def item_sku(self):
        return ItemSkusEnum.AWS_USAGE.value

    @property
    def metric_id(self):
        return UsageMetricTypeEnum.USAGE.value


class DummyFalseProcessor(GenerateItemJournalLines):
    _validator = ValidatorAlwaysFalse

    @property
    def item_sku(self):
        return ItemSkusEnum.AWS_USAGE.value

    @property
    def metric_id(self):
        return UsageMetricTypeEnum.USAGE.value


@pytest.mark.parametrize(
    ("metric_id", "expected_result"),
    [
        (ItemSkusEnum.AWS_USAGE.value, True),
        (ItemSkusEnum.AWS_MARKETPLACE.value, False),
    ],
)
def test_can_process_returns_expected(metric_id, expected_result):
    proc = DummyProcessor(billing_discount_tolerance_rate=1, discount=0)

    can_process = proc.can_process(metric_id)

    assert can_process is expected_result


def test_process_generates_line_validator_true(mock_journal_args, mock_journal_line_factory):
    proc = DummyProcessor(billing_discount_tolerance_rate=1, discount=0)
    args = mock_journal_args()
    args["account_metrics"][UsageMetricTypeEnum.USAGE.value] = {"Service A": Decimal(100)}
    service_invoice_map = args["account_metrics"].get(
        UsageMetricTypeEnum.SERVICE_INVOICE_ENTITY.value, {}
    )
    service_invoice_map["Service A"] = next(
        iter(args["account_invoices"]["invoice_entities"].keys())
    )
    args["account_metrics"][UsageMetricTypeEnum.SERVICE_INVOICE_ENTITY.value] = service_invoice_map

    result_lines = proc.process(**args)

    expected = mock_journal_line_factory(
        service_name="Service A",
        item_external_id=ItemSkusEnum.AWS_USAGE.value,
        price=Decimal(100),
    )
    assert result_lines == [expected]


def test_process_skips_when_validator_false(mock_journal_args):
    proc = DummyFalseProcessor(billing_discount_tolerance_rate=1, discount=0)
    args = mock_journal_args()
    args["account_metrics"][UsageMetricTypeEnum.USAGE.value] = {"Service A": Decimal(100)}

    result_lines = proc.process(**args)

    assert result_lines == []
