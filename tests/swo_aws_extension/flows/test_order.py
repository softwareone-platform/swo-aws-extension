import pytest

from swo_aws_extension.flows.order import (
    CloseAccountContext,
    OrderContext,
    is_change_order,
    is_close_account_flow,
    is_purchase_order,
    is_termination_order,
    is_termination_type_close_account,
    is_termination_type_unlink_account,
    is_unlink_flow,
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

    CloseAccountContext.from_order(order)
    representation = str(order_context)
    assert "Context:" in representation
    assert order_context.order_id in representation
    assert order_context.order_type in representation


def test_is_close_account_flow(order_close_account, order_unlink_account):
    assert is_termination_type_close_account(order_close_account) is True
    assert is_termination_type_close_account(order_unlink_account) is False
    assert is_close_account_flow(order_close_account) is True
    assert is_close_account_flow(order_unlink_account) is False
    assert is_termination_order(order_close_account) is True
    assert is_termination_order(order_unlink_account) is True


def test_is_unlink_flow(order_close_account, order_unlink_account):
    assert is_termination_type_unlink_account(order_unlink_account) is True
    assert is_termination_type_unlink_account(order_close_account) is False
    assert is_termination_order(order_unlink_account) is True
    assert is_termination_order(order_close_account) is True
    assert is_unlink_flow(order_unlink_account) is True
    assert is_unlink_flow(order_close_account) is False


def test_close_account_context(order_close_account):
    context = CloseAccountContext.from_order(order_close_account)
    assert context.order == order_close_account
    assert context.terminating_subscriptions_aws_account_ids == ["123-456-789"]


def test_close_account_context_multiple(
    order_termination_close_account_multiple, order_unlink_account
):
    context = CloseAccountContext.from_order(order_termination_close_account_multiple)
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
