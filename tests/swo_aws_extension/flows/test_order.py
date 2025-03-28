import pytest

from swo_aws_extension.flows.order import (
    PurchaseContext,
    TerminateContext,
)


@pytest.fixture()
def order_context(order):
    return PurchaseContext(order=order, order_id="ORD-123-123")


def test_order_string_representation(order):
    order_context = PurchaseContext(order)
    representation = str(order_context)
    assert "Context:" in representation
    assert order_context.order_id in representation
    assert order_context.order_type in representation

    TerminateContext(order=order)
    representation = str(order_context)
    assert "Context:" in representation
    assert order_context.order_id in representation
    assert order_context.order_type in representation


def test_close_account_context(order_close_account):
    context = TerminateContext(order=order_close_account)
    assert context.order == order_close_account
    assert context.terminating_subscriptions_aws_account_ids == ["1234-5678"]


def test_close_account_context_multiple(
    order_termination_close_account_multiple, order_unlink_account
):
    context = TerminateContext(order=order_termination_close_account_multiple)
    assert context.terminating_subscriptions_aws_account_ids == [
        "000000001",
        "000000002",
        "000000003",
    ]
