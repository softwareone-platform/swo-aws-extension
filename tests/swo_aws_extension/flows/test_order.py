import pytest

from swo_aws_extension.flows.order import (
    OrderContext,
    get_subscription_by_line_and_item_id,
    is_change_order,
    is_purchase_order,
    is_termination_order,
)


def test_is_change_order():
    order = {"type": "Change"}
    assert is_change_order(order) is True

    order = {"type": "Termination"}
    assert is_change_order(order) is False


def test_is_purchase_order():
    order = {"type": "Purchase"}
    assert is_purchase_order(order) is True

    order = {"type": "Termination"}
    assert is_purchase_order(order) is False


def test_is_termination_order():
    order = {"type": "Termination"}
    assert is_termination_order(order) is True

    order = {"type": "Purchase"}
    assert is_termination_order(order) is False


@pytest.fixture()
def order_context():
    return OrderContext(
        order={},
        order_id="ORD-123-123",
        agreement_id="AGR-123-123"
    )


def test_order_string_representation(order_context):
    representation = str(order_context)
    assert "OrderContext" in representation
    assert order_context.order_id in representation
    assert order_context.agreement_id in representation


def test_get_subscription_by_line_and_item_id_found(mocker):
    subscriptions = [
        {
            "lines": [
                {"id": "line_1", "item": {"id": "item_1"}},
                {"id": "line_2", "item": {"id": "item_2"}}
            ]
        },
        {
            "lines": [
                {"id": "line_3", "item": {"id": "item_3"}},
                {"id": "line_4", "item": {"id": "item_4"}}
            ]
        }
    ]
    result = get_subscription_by_line_and_item_id(subscriptions, "item_2", "line_2")
    assert result == subscriptions[0]

def test_get_subscription_by_line_and_item_id_not_found():
    subscriptions = [
        {
            "lines": [
                {"id": "line_1", "item": {"id": "item_1"}},
                {"id": "line_2", "item": {"id": "item_2"}}
            ]
        },
        {
            "lines": [
                {"id": "line_3", "item": {"id": "item_3"}},
                {"id": "line_4", "item": {"id": "item_4"}}
            ]
        }
    ]
    result = get_subscription_by_line_and_item_id(subscriptions, "item_5", "line_5")
    assert result is None
