import pytest

from swo_aws_extension.flows.order import (
    PurchaseContext,
    TerminateContext,
)


@pytest.fixture()
def order_context(order):
    return PurchaseContext.from_order_data(order)


def test_order_string_representation(mock_order):
    order_context = PurchaseContext(mock_order)
    representation = str(order_context)
    assert "Context:" in representation
    assert order_context.order_id in representation
    assert order_context.order_type in representation

    TerminateContext.from_order_data(mock_order)
    representation = str(order_context)
    assert "Context:" in representation
    assert order_context.order_id in representation
    assert order_context.order_type in representation


def test_close_account_context(order_close_account):
    context = TerminateContext.from_order_data(order_close_account)
    assert context.order == order_close_account
    assert context.terminating_subscriptions_aws_account_ids == ["1234-5678"]


def test_close_account_context_multiple(
    order_termination_close_account_multiple, order_unlink_account
):
    context = TerminateContext.from_order_data(order_termination_close_account_multiple)
    assert context.terminating_subscriptions_aws_account_ids == [
        "000000001",
        "000000002",
        "000000003",
    ]


def test_purchase_context_get_account_ids(
    mocker, order_factory, order_parameters_factory, fulfillment_parameters_factory
):
    def create_order(order_ids):
        return order_factory(
            order_parameters=order_parameters_factory(account_id=order_ids),
            fulfillment_parameters=fulfillment_parameters_factory(),
        )

    order_ids = """
    123456789
    123456788
    123456787
    123456789

    """

    context = PurchaseContext.from_order_data(create_order(order_ids))
    assert context.get_account_ids() == {"123456789", "123456787", "123456788"}

    order_ids = ""
    context = PurchaseContext.from_order_data(create_order(order_ids))
    assert context.get_account_ids() == set()

    order_ids = " "
    context = PurchaseContext.from_order_data(create_order(order_ids))
    assert context.get_account_ids() == set()

    order_ids = None
    context = PurchaseContext.from_order_data(create_order(order_ids))
    assert context.get_account_ids() == set()

    order_ids = "123456789"
    context = PurchaseContext.from_order_data(create_order(order_ids))
    assert context.get_account_ids() == {"123456789"}
