import json
from decimal import Decimal

from swo_aws_extension.flows.jobs.billing_journal.models.journal_line import (
    InvoiceDetails,
    JournalDetails,
    JournalLine,
)


def test_to_dict(sample_journal_line):
    result = sample_journal_line.to_dict()

    expected = {
        "description": {"value1": "Service A", "value2": "Account/Entity"},
        "externalIds": {"invoice": "INV-1", "reference": "AGR-1", "vendor": "VND-1"},
        "period": {"start": "2025-01-01", "end": "2025-01-31"},
        "price": {"PPx1": Decimal("10.50"), "UnitPP": Decimal("10.50")},
        "quantity": 2,
        "segment": "COM",
        "search": {
            "item": {"criteria": "item.crit", "value": "ITEM-1"},
            "subscription": {"criteria": "sub.crit", "value": "SUB-1"},
        },
    }
    assert result == expected


def test_to_dict_includes_error_when_present(sample_journal_line):
    sample_journal_line.error = "Some error"

    result = sample_journal_line.to_dict()

    assert result["error"] == "Some error"


def test_is_valid(sample_journal_line):
    sample_journal_line.error = "Error"

    result = sample_journal_line.is_valid()

    assert result is False


def test_to_jsonl(sample_journal_line):
    result = sample_journal_line.to_jsonl()

    assert result.endswith("\n")
    assert json.loads(result.strip())["description"]["value1"] == "Service A"


def test_build():
    journal_details = JournalDetails("AGR-123", "MPA-456", "2025-10-01", "2025-10-31")
    invoice_details = InvoiceDetails("AWS S3", "ACC-789", "ENT-0", "INV-111", Decimal("99.99"))

    result = JournalLine.build(
        item_external_id="EXT-1",
        journal_details=journal_details,
        invoice_details=invoice_details,
        quantity=5,
        segment="EDU",
    )

    expected = {
        "description": {"value1": "AWS S3", "value2": "ACC-789/ENT-0"},
        "externalIds": {"invoice": "INV-111", "reference": "AGR-123", "vendor": "MPA-456"},
        "period": {"start": "2025-10-01", "end": "2025-10-31"},
        "price": {"PPx1": Decimal("99.99"), "UnitPP": Decimal("99.99")},
        "quantity": 5,
        "segment": "EDU",
        "search": {
            "item": {"criteria": "item.externalIds.vendor", "value": "EXT-1"},
            "subscription": {"criteria": "subscription.externalIds.vendor", "value": "ACC-789"},
        },
    }
    assert result.to_dict() == expected


def test_build_with_error_and_no_item():
    journal_details = JournalDetails("AGR", "MPA", "START", "END")
    invoice_details = InvoiceDetails("SVC", "ACC", "ENT", "INV", Decimal(0), error="Missing Item")

    result = JournalLine.build(None, journal_details, invoice_details)

    expected_search_item_value = "Item Not Found"
    assert result.search.search_item.criteria_value == expected_search_item_value
    assert result.error == "Missing Item"
    assert result.is_valid() is False
