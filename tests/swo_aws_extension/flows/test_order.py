import pytest

from swo_aws_extension.flows.order import (
    OrderContext,
    TerminateContext,
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
def order_context(order):
    return OrderContext(order=order, order_id="ORD-123-123")


def test_order_string_representation(order):
    order_context = OrderContext(order)
    representation = str(order_context)
    assert "Context:" in representation
    assert order_context.order_id in representation
    assert order_context.order_type in representation

    TerminateContext.from_order(order)
    representation = str(order_context)
    assert "Context:" in representation
    assert order_context.order_id in representation
    assert order_context.order_type in representation


def test_close_account_context(order_close_account):
    context = TerminateContext.from_order(order_close_account)
    assert context.order == order_close_account
    assert context.terminating_subscriptions_aws_account_ids == ["1234-5678"]


def test_close_account_context_multiple(
    order_termination_close_account_multiple, order_unlink_account
):
    context = TerminateContext.from_order(order_termination_close_account_multiple)
    assert context.terminating_subscriptions_aws_account_ids == [
        "000000001",
        "000000002",
        "000000003",
    ]


def test_order_context_properties(order):
    order_context = OrderContext(order)
    assert order_context.order_id == "ORD-0792-5000-2253-4210"
    assert order_context.order_type == "Purchase"
    assert order_context.mpa_account == "123456789012"


def test_order_context_malformed():
    order_context = OrderContext(None)
    assert order_context.order_id is None
    assert order_context.mpa_account is None
