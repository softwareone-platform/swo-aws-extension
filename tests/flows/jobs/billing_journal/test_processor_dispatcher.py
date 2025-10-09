from swo_aws_extension.flows.jobs.billing_journal.line_processors.base_processor import (
    GenerateItemJournalLines,
)
from swo_aws_extension.flows.jobs.billing_journal.processor_dispatcher import (
    JournalProcessorDispatcher,
)

EXPECTED_PROCESSOR_COUNT = 13


class ProcessorMatch(GenerateItemJournalLines):
    _validator = None

    @property
    def item_sku(self):
        return "SKU_MATCH"

    @property
    def metric_id(self):
        return ""

    def process(self, account_id, account_metrics, journal_details, account_invoices):
        return [f"Processed {self.item_sku}"]


class ProcessorNoMatch(GenerateItemJournalLines):
    _validator = None

    @property
    def item_sku(self):
        return "SKU_NO_MATCH"

    @property
    def metric_id(self):
        return ""

    def process(self, account_id, account_metrics, journal_details, account_invoices):
        return [f"Processed {self.item_sku}"]


def test_dispatcher_calls_matching_processors():
    dispatcher = JournalProcessorDispatcher([ProcessorMatch(0, 0), ProcessorNoMatch(0, 0)])

    expected = dispatcher.process(
        item_sku="SKU_MATCH",
        account_id="account_id",
        account_metrics={},
        journal_details={},
        account_invoices={},
    )

    assert expected == ["Processed SKU_MATCH"]


def test_dispatcher_no_processor_matches():
    dispatcher = JournalProcessorDispatcher([ProcessorMatch(0, 0), ProcessorNoMatch(0, 0)])

    expected = dispatcher.process(
        item_sku="Not found item",
        account_id="account_id",
        account_metrics={},
        journal_details={},
        account_invoices={},
    )

    assert expected == []


def test_create_journal_dispatcher_builds_all(config):
    dispatcher = JournalProcessorDispatcher.build(config)

    processors = dispatcher.processors

    assert len(processors) == EXPECTED_PROCESSOR_COUNT
