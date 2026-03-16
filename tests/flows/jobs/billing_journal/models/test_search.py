from dataclasses import asdict

from swo_aws_extension.flows.jobs.billing_journal.models.search import (
    Search,
    SearchItem,
    SearchSource,
)


def test_search_asdict():
    search = Search(
        search_item=SearchItem("item.criteria", "ITEM-1"),
        source=SearchSource("Subscription", "source.criteria", "SRC-1"),
    )

    result = asdict(search)

    assert result == {
        "search_item": {"criteria": "item.criteria", "criteria_value": "ITEM-1"},
        "source": {
            "type": "Subscription",
            "criteria": "source.criteria",
            "criteria_value": "SRC-1",
        },
    }
