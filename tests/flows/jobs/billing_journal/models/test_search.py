from dataclasses import asdict

from swo_aws_extension.flows.jobs.billing_journal.models.search import (
    Search,
    SearchItem,
    SearchSubscription,
)


def test_search_asdict():
    search = Search(
        search_item=SearchItem("item.criteria", "ITEM-1"),
        subscription=SearchSubscription("sub.criteria", "SUB-1"),
    )

    result = asdict(search)

    assert result == {
        "search_item": {"criteria": "item.criteria", "criteria_value": "ITEM-1"},
        "subscription": {"criteria": "sub.criteria", "criteria_value": "SUB-1"},
    }
